"""Voice level matching.

The Magpie voices come out of the server at whatever level the model
happens to produce: measured on one sentence, Mia sits near -29 LUFS and
Diego near -16, a thirteen-decibel gap, so a two-voice episode had one
host whispering and the other shouting. Every clip is brought to one
target loudness here, right after synthesis, before it is joined to
anything — a guarantee the pipeline gives, not a judgement the agent
has to make each time.

Gain is a plain volume change (no compression, no pumping), computed from
the clip's integrated loudness (EBU R128, via ffmpeg) with a true-peak
ceiling so a loud voice brought up never clips.
"""

import logging
import os
import re
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

TARGET_LUFS = float(os.getenv("TTS_TARGET_LUFS", "-19"))
PEAK_CEILING_DB = -1.5
_I = re.compile(r"I:\s+(-?[\d.]+)\s+LUFS")
_PEAK = re.compile(r"Peak:\s+(-?[\d.]+)\s+dBFS")


def enabled() -> bool:
    return os.getenv("TTS_NORMALIZE", "true").lower() == "true"


def measure(wav: bytes) -> Optional[dict]:
    """{"lufs": integrated loudness, "peak": true peak dBFS} or None."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", "pipe:0",
             "-af", "ebur128=peak=true", "-f", "null", "-"],
            input=wav, capture_output=True, timeout=60,
        )
    except Exception as e:
        logger.debug(f"levels: measure failed ({e})")
        return None
    err = r.stderr.decode("utf-8", "replace")
    tail = err[err.rfind("Summary:"):] if "Summary:" in err else err
    m, p = _I.search(tail), _PEAK.search(tail)
    if not m:
        return None
    lufs = float(m.group(1))
    if lufs <= -60:  # silence or too short to gate
        return None
    return {"lufs": lufs, "peak": float(p.group(1)) if p else None}


def match(wav: bytes, target: float = None) -> bytes:
    """`wav` brought to `target` LUFS by a flat gain, peak-limited. On any
    failure the clip comes back untouched — a level mismatch is better
    than a lost line."""
    if not enabled() or not wav:
        return wav
    target = TARGET_LUFS if target is None else target
    m = measure(wav)
    if not m:
        return wav
    gain = target - m["lufs"]
    if m.get("peak") is not None:
        gain = min(gain, PEAK_CEILING_DB - m["peak"])
    if abs(gain) < 0.5:
        return wav
    # To a file, not a pipe: a WAV written to a pipe cannot have its sizes
    # filled in, and the wave module refuses the result when turns are joined.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = f.name
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", "pipe:0",
             "-af", f"volume={gain:.2f}dB", "-c:a", "pcm_s16le", out],
            input=wav, capture_output=True, timeout=60,
        )
        if r.returncode != 0:
            return wav
        with open(out, "rb") as f:
            data = f.read()
    except Exception as e:
        logger.debug(f"levels: gain failed ({e})")
        return wav
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass
    if not data:
        return wav
    logger.debug(f"levels: {m['lufs']:.1f} LUFS -> {target:.0f} ({gain:+.1f} dB)")
    return data
