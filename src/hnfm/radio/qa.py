"""Listening before airing (issue #32).

Two checks, both local and both cheap. The round trip transcribes what the
voice model said and compares it with the script: a name it could not
pronounce or a sentence it dropped shows up as a low match. The level
check reads the finished file's loudness and length.

Neither check can say a piece is good. They say it is what was written,
and that it is the right loudness. That is still more than nothing
listening to it, which is what happened before.
"""

import difflib
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# A line whose transcript matches its script less than this is voiced again.
MIN_LINE = float(os.getenv("RADIO_QA_MIN_LINE", "0.72"))
# A piece whose lines average less than this does not air.
MIN_PIECE = float(os.getenv("RADIO_QA_MIN_PIECE", "0.80"))
# The station's loudness window, in LUFS, and the least a file may run.
LUFS_WINDOW = (-20.0, -13.0)
MIN_SECONDS = 1.5


def enabled() -> bool:
    return os.getenv("RADIO_QA", "true").strip().lower() != "false"


def _words(text: str) -> list:
    """Script and transcript in one spelling: lower case, numbers as
    words, letters of an acronym run together ("G.P.U." and "GPU" and
    "g p u" are the same thing said)."""
    from .copy import speakable

    t = speakable(text or "").lower()
    t = re.sub(r"\b((?:[a-z]\.){2,})", lambda m: m.group(1).replace(".", ""), t)
    t = re.sub(r"[^a-z0-9' ]", " ", t.replace("-", " "))
    return t.split()


def match(script: str, heard: str) -> float:
    """0..1: how much of the script the transcript contains, in order."""
    a, b = _words(script), _words(heard)
    if not a:
        return 1.0
    if not b:
        return 0.0
    # Join spelled letters the recogniser split: "g p u" -> "gpu".
    def squash(ws):
        out, run = [], []
        for w in ws + [""]:
            if len(w) == 1 and w.isalpha():
                run.append(w)
                continue
            if run:
                out.append("".join(run))
                run = []
            if w:
                out.append(w)
        return out

    a, b = squash(a), squash(b)
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3)


def transcribe(wav_bytes: bytes) -> Optional[str]:
    """What the recogniser hears in a clip, or None if it is away."""
    import requests

    base = (os.getenv("ASR_BASE_URL") or "").rstrip("/")
    if not base:
        return None
    try:
        r = requests.post(
            f"{base}/v1/audio/transcriptions",
            files={"file": ("line.wav", wav_bytes, "audio/wav")},
            data={"model": os.getenv("ASR_MODEL", "nemotron")},
            timeout=int(os.getenv("RADIO_QA_TIMEOUT", "30")),
        )
        if r.status_code != 200:
            logger.debug(f"radio qa: recogniser said {r.status_code}")
            return None
        return (r.json() or {}).get("text") or ""
    except Exception as e:
        logger.debug(f"radio qa: recogniser away ({e})")
        return None


def round_trip(script: str, wav_bytes: bytes) -> Optional[float]:
    """Match of one spoken line against its script; None if it could not
    be checked (which is not a failure: the station airs unchecked rather
    than not at all)."""
    if not enabled():
        return None
    heard = transcribe(wav_bytes)
    return None if heard is None else match(script, heard)


def levels_ok(m: Optional[dict]) -> bool:
    if not m:
        return True  # could not measure; do not block on the meter
    if m.get("seconds") is not None and m["seconds"] < MIN_SECONDS:
        return False
    return LUFS_WINDOW[0] <= m["lufs"] <= LUFS_WINDOW[1]
