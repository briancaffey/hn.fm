"""Inference Club: the one way hn.fm reaches the home lab's media models.

Images and voice go through the club's OpenAI-style API instead of straight
to each model service. The club records every request and its output, files
it into a **collection** (a project folder: `hn.fm/story-<id>`), and keeps it
private. So everything hn.fm makes can be found again, by story, in the
club's gallery.

    hn.fm ──► club /v1/images/generations  ──► agent ──► FLUX 3 Klein (4090)
          ──► club /v1/audio/speech        ──► agent ──► Magpie TTS
          ──► club /v1/catalog             (what exists right now)

Text (the LLM) stays on LiteLLM: triage alone makes hundreds of calls a day
and would bury everything else in the gallery.

If the club is off, unreachable or refuses, the caller falls back to the
direct service and logs it: production never stops because of the club.

Settings:
    INFERENCE_CLUB_ENABLED   "true" to route through the club
    INFERENCE_CLUB_BASE_URL  e.g. http://backend.inference-club-web.svc.cluster.local:8001
    INFERENCE_CLUB_HOST      Host header the club accepts (default club.lan)
    INFERENCE_CLUB_API_KEY   the club API token
    CLUB_IMAGE_MODEL         default flux-3-image-klein-fp8
    CLUB_TTS_MODEL           default magpie-tts-multilingual
"""

import base64
import contextvars
import logging
import os
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# The collection the current piece of work files into. Set per story by the
# pipeline (`filing(item_id)`); everything else lands in plain `hn.fm`.
_collection: contextvars.ContextVar[str] = contextvars.ContextVar("club_collection", default="hn.fm")

# After a failure, skip the club for a short while instead of paying a
# timeout on every image of a story.
_COOLDOWN = 120.0
_down_until = 0.0


class ClubError(RuntimeError):
    pass


def enabled() -> bool:
    return (os.getenv("INFERENCE_CLUB_ENABLED", "false").lower() == "true"
            and bool(os.getenv("INFERENCE_CLUB_BASE_URL")) and bool(os.getenv("INFERENCE_CLUB_API_KEY")))


def usable() -> bool:
    return enabled() and time.time() >= _down_until


def _base() -> str:
    return os.getenv("INFERENCE_CLUB_BASE_URL", "").rstrip("/") + "/v1"


def _headers(json_body: bool = True) -> Dict[str, str]:
    h = {"Authorization": f"Bearer {os.getenv('INFERENCE_CLUB_API_KEY', '')}",
         "Host": os.getenv("INFERENCE_CLUB_HOST", "club.lan")}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def collection() -> str:
    return _collection.get()


class filing:
    """`with club.filing(item_id):` files everything made inside into the
    story's collection."""

    def __init__(self, item_id=None, name: Optional[str] = None):
        self.name = name or (f"hn.fm/story-{item_id}" if item_id else "hn.fm")

    def __enter__(self):
        self._token = _collection.set(self.name)
        return self

    def __exit__(self, *exc):
        _collection.reset(self._token)
        return False


def _fail(why: str) -> None:
    global _down_until
    _down_until = time.time() + _COOLDOWN
    raise ClubError(why)


def _post(path: str, body: Dict, timeout: float) -> requests.Response:
    body = {**body, "collection": collection(), "visibility": "PRIVATE"}
    try:
        r = requests.post(_base() + path, json=body, headers=_headers(), timeout=timeout)
    except requests.RequestException as e:
        _fail(f"the club did not answer: {e}")
    if r.status_code != 200:
        _fail(f"the club said {r.status_code}: {r.text[:200]}")
    return r


def image(prompt: str, width: int, height: int, timeout: float = 300) -> str:
    """One image as base64 PNG."""
    r = _post("/images/generations", {
        "model": os.getenv("CLUB_IMAGE_MODEL", "flux-3-image-klein-fp8"),
        "prompt": prompt, "n": 1, "size": f"{width}x{height}", "response_format": "b64_json",
    }, timeout)
    data = (r.json() or {}).get("data") or []
    if not data or not data[0].get("b64_json"):
        _fail("the club returned no image")
    return data[0]["b64_json"]


def speech(text: str, voice: str, language: str, sample_rate: int, timeout: float = 120) -> bytes:
    """One clip of speech as WAV bytes."""
    r = _post("/audio/speech", {
        "model": os.getenv("CLUB_TTS_MODEL", "magpie-tts-multilingual"),
        "input": text, "voice": voice, "language": language,
        "sample_rate_hz": sample_rate, "response_format": "wav",
    }, timeout)
    if r.headers.get("content-type", "").startswith("application/json"):
        d = r.json() or {}
        b64 = d.get("b64_json") or d.get("audio") or (d.get("data") or [{}])[0].get("b64_json")
        if not b64:
            _fail("the club returned no audio")
        return base64.b64decode(b64)
    if not r.content:
        _fail("the club returned no audio")
    return r.content


def catalog(timeout: float = 10) -> Dict:
    """Every service, model and node the club can reach right now
    (`GET /v1/catalog`). Empty dict when the club is off or unreachable."""
    if not enabled():
        return {}
    try:
        r = requests.get(_base() + "/catalog", headers=_headers(False), timeout=timeout)
        return r.json() if r.status_code == 200 else {}
    except (requests.RequestException, ValueError):
        return {}
