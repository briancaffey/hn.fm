"""Talking to Hermes, the agent that writes the scenes.

hn.fm speaks to one Hermes profile of its own (`hnfm`) over the agent's
HTTP API. That profile has no tools and its own key: what it is sent is
written from pages by strangers, so it is given nothing it could be talked
into misusing. The skill it works from (`skill/SKILL.md`, beside this
file) is sent with each request as the run's instructions.

A run is submitted and polled rather than held open: a scene can take a
minute, and a held connection through a restart is a lost scene.
"""

import logging
import os
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

SKILL = "hnfm-video"


def base() -> str:
    """The profile's API root, or '' when no agent is configured."""
    root = (os.getenv("HERMES_BASE_URL") or "").rstrip("/")
    if not root:
        return ""
    profile = os.getenv("HERMES_PROFILE", "hnfm").strip()
    return f"{root}/p/{profile}" if profile and profile != "default" else root


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {os.getenv('HERMES_API_KEY', '')}", "Content-Type": "application/json"}


def configured() -> bool:
    return bool(base() and os.getenv("HERMES_API_KEY"))


class AgentError(RuntimeError):
    pass


def ask(text: str, *, instructions: Optional[str] = None, session: Optional[str] = None,
        timeout: Optional[int] = None) -> Dict:
    """One turn. Returns {text, seconds, tokens, model, run_id}; raises
    AgentError when the agent is away, refuses, or runs out of time."""
    if not configured():
        raise AgentError("no agent is configured (HERMES_BASE_URL and HERMES_API_KEY)")
    timeout = int(timeout or os.getenv("HERMES_TIMEOUT_SECONDS", "300"))
    body = {"input": text}
    if instructions:
        body["instructions"] = instructions
    if session:
        body["session_id"] = session
    started = time.time()
    try:
        r = requests.post(f"{base()}/v1/runs", headers=_headers(), json=body, timeout=30)
    except requests.RequestException as e:
        raise AgentError(f"the agent did not answer: {e}") from e
    if r.status_code not in (200, 202):
        raise AgentError(f"the agent refused the run: {r.status_code} {r.text[:200]}")
    run_id = (r.json() or {}).get("run_id")
    if not run_id:
        raise AgentError(f"the agent returned no run: {r.text[:200]}")

    status = {}
    while time.time() - started < timeout:
        time.sleep(1.5)
        try:
            status = requests.get(f"{base()}/v1/runs/{run_id}", headers=_headers(), timeout=20).json() or {}
        except (requests.RequestException, ValueError):
            continue
        state = status.get("status")
        if state == "completed":
            usage = status.get("usage") or {}
            return {"text": status.get("output") or "", "seconds": round(time.time() - started, 1),
                    "tokens": int(usage.get("total_tokens") or 0),
                    "model": (status.get("runtime") or {}).get("model") or "", "run_id": run_id}
        if state in ("failed", "cancelled", "interrupted"):
            raise AgentError(f"the run {state}: {str(status.get('error') or status.get('output') or '')[:200]}")
    try:
        requests.post(f"{base()}/v1/runs/{run_id}/stop", headers=_headers(), timeout=10)
    except requests.RequestException:
        pass
    raise AgentError(f"the agent took longer than {timeout}s")


def ping() -> str:
    """One real turn, for the inference check: is the profile there, does
    it hold the skill, does it answer."""
    if not configured():
        raise AgentError("no agent is configured")
    r = requests.get(f"{base()}/v1/toolsets", headers=_headers(), timeout=10)
    if r.status_code != 200:
        raise AgentError(f"the agent's API said {r.status_code}")
    rows = (r.json() or {}).get("data") or (r.json() or {}).get("toolsets") or []
    tools = sorted(t["name"] for t in rows if t.get("enabled"))
    got = ask("Reply with the single word: ready", timeout=90)
    return f"{got['model'] or 'agent'} answered in {got['seconds']}s; tools: {', '.join(tools) or 'none'}"
