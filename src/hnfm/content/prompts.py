"""Versioned prompt registry (plans/08-llm-foundation.md).

Prompts are the product here — nearly every quality change in plans 9-15 is a
prompt edit. Left as Python string literals they can't be diffed against an
output, attributed to a run, or rolled back. So they live in `prompts/*.yaml`
with a `version`, and every LLM call records which prompt version produced it.

That recorded version is what makes plan 14's evals answerable: "the script
score dropped on 2026-08-20" becomes "script.write went v3 → v4 that day."

Format:

    name: script.write
    version: 3
    task: script.write          # selects an llm_profiles entry
    description: one line, for humans
    system: |                   # optional
      ...
    template: |                 # {placeholders} filled by render()
      ...
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

logger = logging.getLogger(__name__)


def prompts_dir() -> Path:
    """`prompts/` at the project root, or $PROMPTS_DIR.

    Resolved from this file rather than the cwd: Celery workers, pytest and the
    API server all start from different directories, and a prompt that silently
    fails to load would fall back to a stale inline default.
    """
    override = os.getenv("PROMPTS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "prompts"


@dataclass(frozen=True)
class RenderedPrompt:
    """A prompt ready to send, carrying the provenance needed to record it."""

    text: str
    name: str
    version: str
    task: Optional[str] = None
    system: Optional[str] = None

    def __str__(self) -> str:  # so it can be passed anywhere a str is expected
        return self.text


class PromptNotFound(RuntimeError):
    pass


class PromptRegistry:
    """Loads and renders versioned prompts. Cached, with an env escape hatch
    for editing prompts against a live worker."""

    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory) if directory else prompts_dir()
        self._cache: Dict[str, dict] = {}

    def _reload_always(self) -> bool:
        return os.getenv("PROMPTS_NO_CACHE", "").lower() in ("1", "true", "yes")

    def load(self, name: str) -> dict:
        if not self._reload_always() and name in self._cache:
            return self._cache[name]

        path = self.directory / f"{name}.yaml"
        if not path.exists():
            raise PromptNotFound(
                f"prompt {name!r} not found at {path}. Prompts are versioned "
                f"files, not inline strings — add it rather than hardcoding."
            )
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for required in ("version", "template"):
            if required not in data:
                raise PromptNotFound(f"prompt {name!r} is missing {required!r}")
        data.setdefault("name", name)
        data.setdefault("task", name)

        self._cache[name] = data
        return data

    def render(self, name: str, **variables) -> RenderedPrompt:
        """Fill a prompt's template. Missing placeholders raise rather than
        rendering a prompt with a literal `{summary}` in it."""
        data = self.load(name)
        template = data["template"]
        try:
            body = template.format(**variables)
        except KeyError as e:
            raise KeyError(
                f"prompt {name!r} (v{data['version']}) needs variable {e} "
                f"— got {sorted(variables)}"
            ) from e

        system = data.get("system")
        text = f"{system.strip()}\n\n{body.strip()}" if system else body.strip()
        return RenderedPrompt(
            text=text,
            name=data["name"],
            version=str(data["version"]),
            task=data.get("task"),
            system=system,
        )

    def list_prompts(self) -> Dict[str, str]:
        """name -> version, for the UI and for eval scorecards."""
        out = {}
        for path in sorted(self.directory.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                out[path.stem] = str(data.get("version", "?"))
            except Exception as e:
                logger.warning(f"could not read prompt {path.name}: {e}")
        return out


_registry: Optional[PromptRegistry] = None


def registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


def render(name: str, **variables) -> RenderedPrompt:
    return registry().render(name, **variables)
