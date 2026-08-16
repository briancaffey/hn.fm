"""LLM service for hn.fm (plans/08-llm-foundation.md).

Two entry points:

- `generate_content()`  — prose out (summaries, scenes, haiku).
- `generate_structured()` — a validated Pydantic model out, via the
  OpenAI-compatible `response_format: json_schema`.

**Failures raise.** This module used to catch every exception and return the
literal string `"[S1] This is a fallback, error generating script"`. A dead LLM
therefore produced a *successful* run, and the pipeline went on to spend Flux
and LTX GPU time rendering a one-line garbage script. Callers that can
genuinely proceed without a result (emoji, haiku, tags) handle that themselves
— see the `_safe()` helper in `web/tasks.process_hn_item_run`. Silence is not
a default this project can afford.

Every call is checked against the model allowlist before and after the request
(`content/model_policy.py`), because the gateway can fail over server-side to a
paid route.
"""

import json
import logging
import os
from typing import Optional, Type, TypeVar, Union

import openai
from pydantic import BaseModel, ValidationError

from . import model_policy
from .llm_schemas import to_strict_schema
from .prompts import RenderedPrompt

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

PromptLike = Union[str, RenderedPrompt]

DEFAULT_SYSTEM = (
    "You are a helpful AI assistant that generates high-quality content "
    "based on user requests."
)


class LLMError(RuntimeError):
    """The LLM did not produce a usable result."""


class LLMService:
    """Client for the configured LLM gateway."""

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        task: str = None,
    ):
        """
        Args:
            base_url: gateway base URL; defaults to $LLM_BASE_URL
            model: explicit model override; otherwise resolved from the task
                profile, then $LLM_MODEL
            task: profile key in config.yaml `llm.profiles` (e.g. "script.write")
        """
        self.task = task
        self.profile = _profile_for(task)
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.model = (
            model
            or self.profile.get("model")
            or os.getenv("LLM_MODEL", "nvidia-nemotron-super")
        )
        self.fallback_model = self.profile.get("fallback_model")
        self.temperature = float(self.profile.get("temperature", 0.7))
        self.max_tokens = int(self.profile.get("max_tokens", 2000))
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.use_local = bool(self.base_url)

        # Fail before the call, not after the bill.
        model_policy.check_request(self.model)
        if self.fallback_model:
            model_policy.check_request(self.fallback_model)

        self.client = self._build_client()

    def _build_client(self):
        if self.use_local:
            api_url = self.base_url
            if not api_url.endswith("/v1"):
                api_url = api_url.rstrip("/") + "/v1"
            # Gateways like LiteLLM require the real key; bare local servers
            # ignore it.
            return openai.OpenAI(api_key=self.api_key or "not-needed", base_url=api_url)
        if self.api_key:
            return openai.OpenAI(api_key=self.api_key)
        raise LLMError(
            "No LLM configured: set LLM_BASE_URL (gateway) or OPENAI_API_KEY. "
            "There is deliberately no silent fallback — a missing LLM must "
            "fail the step rather than produce placeholder content."
        )

    # -- internals ---------------------------------------------------------

    def _models_to_try(self) -> list:
        return [m for m in (self.model, self.fallback_model) if m]

    def _call(
        self,
        model: str,
        prompt: PromptLike,
        response_format=None,
        image_b64: Optional[str] = None,
    ) -> str:
        """One completion. Raises on any failure — no fallback content."""
        text = prompt.text if isinstance(prompt, RenderedPrompt) else str(prompt)
        system = (
            prompt.system
            if isinstance(prompt, RenderedPrompt) and prompt.system
            else DEFAULT_SYSTEM
        )

        if image_b64:
            user_content = [
                {"type": "text", "text": text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
            ]
        else:
            user_content = text

        kwargs = dict(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        if response_format is not None:
            kwargs["response_format"] = response_format
        if self.use_local:
            # Reasoning models otherwise emit only `reasoning_content` with null
            # content. Required even alongside response_format: a JSON schema
            # suppresses the preamble on `nvidia-nemotron-super` but NOT on the
            # multimodal `nemotron-omni` route, which returns null content until
            # thinking is disabled. The two options compose fine.
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}

        response = self.client.chat.completions.create(**kwargs)
        self._record_usage(response, model, prompt)
        model_policy.check_response(model, getattr(response, "model", None))

        if not getattr(response, "choices", None):
            error = getattr(response, "error", None)
            raise LLMError(
                f"{model} returned no choices" + (f": {error}" if error else "")
            )

        message = response.choices[0].message
        content = getattr(message, "content", None) or getattr(
            message, "reasoning_content", None
        )
        if not content or not content.strip():
            raise LLMError(f"{model} returned empty content")
        return content

    def _record_usage(self, response, model: str, prompt: PromptLike) -> None:
        """Attribute tokens and the prompt version to the current audit step."""
        try:
            usage = getattr(response, "usage", None)
            if not usage:
                return
            tokens_in = getattr(usage, "prompt_tokens", 0)
            tokens_out = getattr(usage, "completion_tokens", 0)

            from ..utils.metrics import record_tokens

            record_tokens(tokens_in, tokens_out)

            from ..db import steps

            steps.record_llm(
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                prompt_name=getattr(prompt, "name", None),
                prompt_version=getattr(prompt, "version", None),
            )
        except Exception as e:  # recording must never break generation
            logger.debug(f"usage recording failed (non-fatal): {e}")

    # -- public API --------------------------------------------------------

    def generate_content(self, prompt: PromptLike) -> str:
        """Prose. Tries the profile's model, then its fallback. Raises if none
        succeed — callers decide whether that is fatal."""
        errors = []
        for model in self._models_to_try():
            try:
                content = self._call(model, prompt)
                logger.debug(f"✅ {model}: {content[:60]}...")
                return content
            except Exception as e:
                errors.append(f"{model}: {e}")
                logger.warning(f"LLM call failed on {model}: {e}")
        raise LLMError(f"all models failed — {'; '.join(errors)}")

    def generate_structured_vision(
        self, prompt: PromptLike, schema: Type[T], *, image_b64: str, **kwargs
    ) -> T:
        """`generate_structured` with an image attached (the sequence planner's
        look-at-the-rendered-frame call)."""
        return self.generate_structured(prompt, schema, image_b64=image_b64, **kwargs)

    def generate_structured(
        self,
        prompt: PromptLike,
        schema: Type[T],
        *,
        max_attempts: int = 2,
        image_b64: Optional[str] = None,
    ) -> T:
        """A validated instance of `schema`.

        Constrained decoding does the heavy lifting; the retry exists because
        adherence is not a guarantee across routes. On a validation failure the
        error is fed back so the model can correct itself, rather than silently
        substituting a default.
        """
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "strict": True,
                "schema": to_strict_schema(schema),
            },
        }

        errors = []
        for model in self._models_to_try():
            attempt_prompt = prompt
            for attempt in range(1, max_attempts + 1):
                try:
                    raw = self._call(
                        model, attempt_prompt, response_format, image_b64=image_b64
                    )
                    return schema.model_validate_json(_strip_fences(raw))
                except ValidationError as e:
                    detail = _short(e)
                    errors.append(f"{model} attempt {attempt}: {detail}")
                    logger.warning(f"structured output invalid ({model}): {detail}")
                    base = (
                        attempt_prompt.text
                        if isinstance(attempt_prompt, RenderedPrompt)
                        else str(attempt_prompt)
                    )
                    attempt_prompt = (
                        f"{base}\n\nYour previous reply did not match the required "
                        f"schema: {detail}\nReturn ONLY valid JSON matching the schema."
                    )
                except json.JSONDecodeError as e:
                    errors.append(f"{model} attempt {attempt}: not JSON ({e})")
                    logger.warning(f"structured output was not JSON ({model}): {e}")
                except Exception as e:
                    errors.append(f"{model} attempt {attempt}: {e}")
                    logger.warning(f"structured call failed ({model}): {e}")
                    break  # transport/policy failure — try the next model

        raise LLMError(
            f"structured generation failed for {schema.__name__} — {'; '.join(errors)}"
        )


def _strip_fences(text: str) -> str:
    """Defensive only. Constrained decoding returns bare JSON, but a route that
    quietly ignores `response_format` would wrap it."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    return text.strip().removeprefix("json").strip()


def _short(error: ValidationError, limit: int = 300) -> str:
    parts = [
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()[:4]
    ]
    return "; ".join(parts)[:limit]


def _profile_for(task: Optional[str]) -> dict:
    """Per-task model settings from config.yaml `llm.profiles`.

    One model at a fixed temperature served triage, summaries, scripts, image
    prompts and the director. Those want different settings — a fact extractor
    should not run at the same temperature as a scene writer.
    """
    if not task:
        return {}
    try:
        from ..utils.config import config_manager

        profiles = (config_manager.get("llm", {}) or {}).get("profiles", {}) or {}
        return profiles.get(task, {}) or {}
    except Exception as e:
        logger.debug(f"profile lookup failed for {task!r} (non-fatal): {e}")
        return {}
