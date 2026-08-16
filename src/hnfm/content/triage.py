"""Story triage: score a processed run's suitability for an engaging video.

Runs on the cheap text half of the pipeline (scrape + summary already done),
so every candidate story can be scored before any GPU time is spent. The
rubric and interest profile live in config.yaml (`triage:`) — data, not code.

Models: free LiteLLM routes only. Primary + fallback are configured; the
env var TRIAGE_LLM_MODEL overrides the primary.
"""

import json
import logging
import math
import os
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

VERDICTS = ("great", "good", "marginal", "unsuitable")

# Deterministic hard flags (found before/without the LLM)
FLAG_SCRAPE_FALLBACK = "scrape_fallback"
FLAG_TOO_SHORT = "too_short"

_PROMPT = """You are a video producer triaging Hacker News stories for a channel
that turns tech stories into short narrated videos with AI-generated visuals.

Rubric:
{rubric}

Story title: {title}
HN score: {hn_score} | comments: {comments}
Summary of the article:
{summary}

Content excerpt:
{excerpt}

Respond with ONLY a JSON object (no markdown fences, no commentary):
{{
  "suitability": <0-100 integer, overall fitness for an engaging video>,
  "verdict": "great" | "good" | "marginal" | "unsuitable",
  "reasons": [<2-3 short strings explaining the score>],
  "flags": [<zero or more of: "paywalled_partial", "niche_library", "listicle", "no_narrative", "low_visual_potential", "corporate_pr", "outdated">],
  "topics": [<3-6 lowercase kebab-case topic tags, e.g. "generative-ai", "local-ai", "security", "hardware", "programming-languages">],
  "visual_potential": <0-10, can this be SHOWN, not just said>,
  "narrative_potential": <0-10, is there a story arc / tension / stakes>
}}"""


def _triage_config() -> dict:
    from ..utils.config import config_manager

    return config_manager.get("triage", {}) or {}


def primary_model() -> str:
    return os.getenv("TRIAGE_LLM_MODEL") or _triage_config().get(
        "model", "nvidia-nemotron-super"
    )


def fallback_model() -> Optional[str]:
    return _triage_config().get("fallback_model", "openrouter-nemotron-ultra")


def _extract_json(text: str) -> Optional[dict]:
    """Tolerant JSON extraction: strip fences/reasoning, find the outermost
    object. Reasoning models love to decorate their answers."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _normalize(data: dict) -> dict:
    """Clamp/clean LLM output so bad values can't corrupt the queue."""
    def _int(v, lo, hi, default=0):
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return default

    verdict = str(data.get("verdict", "")).lower()
    if verdict not in VERDICTS:
        verdict = "marginal"
    return {
        "suitability": _int(data.get("suitability"), 0, 100),
        "verdict": verdict,
        "reasons": [str(r)[:300] for r in (data.get("reasons") or [])][:5],
        "flags": [str(f)[:60] for f in (data.get("flags") or [])][:10],
        "topics": [str(t).lower()[:60] for t in (data.get("topics") or [])][:8],
        "visual_potential": _int(data.get("visual_potential"), 0, 10),
        "narrative_potential": _int(data.get("narrative_potential"), 0, 10),
    }


def score_content(title: str, summary: str, content_clean: str,
                  hn_score: int = 0, comments: int = 0) -> dict:
    """LLM suitability score. Tries the primary free model, then the fallback.
    Raises RuntimeError if neither produces parseable JSON."""
    from .llm_service import LLMService

    cfg = _triage_config()
    prompt = _PROMPT.format(
        rubric=(cfg.get("rubric") or "Favor engaging, visual, comprehensible stories."),
        title=title or "(untitled)",
        hn_score=hn_score or 0,
        comments=comments or 0,
        summary=(summary or "")[:2000],
        excerpt=(content_clean or "")[:3000],
    )

    last_error = None
    for model in [m for m in (primary_model(), fallback_model()) if m]:
        try:
            service = LLMService(model=model)
            raw = service.generate_content(prompt)
            data = _extract_json(raw or "")
            if data:
                result = _normalize(data)
                result["model"] = model
                return result
            last_error = f"unparseable response from {model}"
            logger.warning(f"triage: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"triage model {model} failed: {e}")
    raise RuntimeError(f"triage scoring failed: {last_error}")


def interest_match(topics: list, title: str = "") -> float:
    """Weighted overlap between story topics and the configured interest
    profile, squashed to [-1, 1]."""
    profile = _triage_config().get("interest_profile") or {}
    if not profile:
        return 0.0
    haystacks = [t.lower() for t in (topics or [])] + [(title or "").lower()]
    total = 0.0
    for keyword, weight in profile.items():
        kw = str(keyword).lower()
        if any(kw in h for h in haystacks):
            total += float(weight)
    return math.tanh(total / 3.0)


def rank_score(suitability: int, interest: float, hn_score: int) -> float:
    weights = _triage_config().get("weights") or {}
    w_suit = float(weights.get("suitability", 1.0))
    w_int = float(weights.get("interest", 0.6))
    w_hn = float(weights.get("hn_score", 0.4))
    return round(
        w_suit * suitability
        + w_int * interest * 100.0
        + w_hn * math.log10((hn_score or 0) + 1) * 25.0,
        2,
    )


def hard_flags(content_clean: str, scrape_fallback: bool) -> list:
    flags = []
    if scrape_fallback:
        flags.append(FLAG_SCRAPE_FALLBACK)
    if len(content_clean or "") < 400:
        flags.append(FLAG_TOO_SHORT)
    return flags
