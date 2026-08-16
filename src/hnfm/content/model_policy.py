"""Model allowlist — the guardrail against silently spending money.

Brian's standing rule for this project is FREE routes only: no groq, nothing
paid. Two things make that easy to violate by accident:

1. The LiteLLM gateway advertises 221 routes, including `groq-llama-3.3-70b`
   and ~200 `lmstudio/*` entries mirroring the full commercial OpenAI catalog
   (gpt-5.x, o3-pro, sora-2). A typo in a config value reaches one of them.
2. **Server-side failover.** A gateway route can fail over to a different
   upstream than the one requested — the `nemotron-omni` route has been
   observed falling back to groq when the local box is down. The request looks
   correct; the *response* is what reveals the substitution.

So this module checks both ends: `check_request()` before the call, and
`check_response()` on the model the gateway says it actually served. The
second check is the one that catches failover, and it is the reason this is a
module rather than an `if` statement at one call site.

Policy lives in config.yaml under `llm.models:` — data, not code, like the
triage rubric.
"""

import fnmatch
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

# Used when config.yaml carries no policy at all. Deliberately the three free
# nemotron routes and nothing else — a missing config must fail closed, not open.
DEFAULT_ALLOW = ["nvidia-nemotron-super", "openrouter-nemotron-ultra", "nemotron-omni"]

# Checked before the allowlist so a broad wildcard can't accidentally re-admit a
# route Brian has explicitly ruled out.
DEFAULT_DENY = ["groq*", "*/groq*"]


class ModelNotAllowed(RuntimeError):
    """A call targeted, or was served by, a route outside the policy."""


def _policy() -> dict:
    from ..utils.config import config_manager

    return (config_manager.get("llm", {}) or {}).get("models", {}) or {}


def allowed_patterns() -> List[str]:
    return list(_policy().get("allow") or DEFAULT_ALLOW)


def denied_patterns() -> List[str]:
    return list(_policy().get("deny") or DEFAULT_DENY)


def _matches(model: str, patterns: List[str]) -> Optional[str]:
    """The first pattern `model` matches, or None. Exact names work because
    fnmatch treats a pattern with no metacharacters as a literal."""
    for pattern in patterns:
        if fnmatch.fnmatch(model, pattern):
            return pattern
    return None


def is_allowed(model: str) -> bool:
    if not model:
        return False
    if _matches(model, denied_patterns()):
        return False
    return _matches(model, allowed_patterns()) is not None


def check_request(model: str) -> None:
    """Raise before spending anything on a route outside the policy."""
    if not model:
        raise ModelNotAllowed("no model configured for this call")

    denied_by = _matches(model, denied_patterns())
    if denied_by:
        raise ModelNotAllowed(
            f"model {model!r} is explicitly denied (matched {denied_by!r}). "
            f"This project runs on free routes only."
        )

    if not _matches(model, allowed_patterns()):
        raise ModelNotAllowed(
            f"model {model!r} is not in the allowlist {allowed_patterns()}. "
            f"If this route is genuinely free, add it to `llm.models.allow` in "
            f"config.yaml — do not widen the list to a bare wildcard."
        )


def check_response(requested: str, served: Optional[str]) -> None:
    """Verify the gateway served what we asked for.

    A substitution is not fatal by itself — the tokens are already spent, and
    raising here would throw away a usable answer. But it must be loud, because
    silent failover to a paid route is exactly the failure this project cannot
    afford to discover from a bill. `LLM_STRICT_MODEL=1` upgrades it to fatal.
    """
    if not served or served == requested:
        return

    if not is_allowed(served):
        message = (
            f"⚠️  MODEL SUBSTITUTION: requested {requested!r} but the gateway "
            f"served {served!r}, which is NOT in the allowlist. The gateway "
            f"likely failed over. Check that the upstream for {requested!r} is up."
        )
        logger.error(message)
        if os.getenv("LLM_STRICT_MODEL", "").lower() in ("1", "true", "yes"):
            raise ModelNotAllowed(message)
    else:
        logger.warning(
            f"gateway served {served!r} for a {requested!r} request "
            f"(both allowed, but the substitution is worth knowing about)"
        )
