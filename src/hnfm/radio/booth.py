"""The booth: a written piece becomes a finished file (issues #31, #32).

Each line is spoken in its voice, checked by ear (the round trip in
qa.py) and spoken again if it came out wrong. The lines are joined with a
beat between turns, callers down a phone line, and the result is mixed by
the segment's recipe: plain, over a ducking bed, or after a sting.

    record(piece, seg, ...) -> {path, seconds, qa} or None
"""

import logging
import os
import tempfile
from typing import List, Optional

from . import mix, qa
from .segments import Segment
from .voice import is_caller, speak

logger = logging.getLogger(__name__)

# The beat after a line, by who spoke and who is next.
GAP_SAME, GAP_TURN, GAP_PHONE = 220, 300, 420


def _gap(line: dict, nxt: Optional[dict]) -> int:
    if nxt is None:
        return 0
    if is_caller(line["speaker"]) or is_caller(nxt["speaker"]):
        return GAP_PHONE
    return GAP_SAME if line["speaker"] == nxt["speaker"] else GAP_TURN


def _take(line: dict, seed: int) -> tuple:
    """(wav bytes, match) for one line: spoken, heard back, and spoken
    again in the plain voice if the first take does not match its script."""
    wav = speak(line["text"], line["speaker"], line.get("mood"), seed)
    if not wav:
        return None, None
    score = qa.round_trip(line["text"], wav)
    if score is not None and score < qa.MIN_LINE:
        retry = speak(line["text"], line["speaker"], "default" if line.get("mood") != "default" else "neutral",
                      seed, fresh=line.get("mood") == "default")
        if retry:
            again = qa.round_trip(line["text"], retry)
            if again is not None and again > score:
                return retry, again
    return wav, score


def record(lines: List[dict], seg: Segment, out_mp3: str, *, bed: Optional[str] = None,
           sting: Optional[str] = None, seed: int = 0) -> Optional[dict]:
    """Speak, check and mix a piece. None if it cannot air: a voice was
    away, or what was said is not what was written."""
    # Beside the outputs, not in the system temp directory: the finished
    # file is then a rename away, on the same filesystem.
    from . import radio_root

    base = os.path.join(radio_root(), "tmp")
    os.makedirs(base, exist_ok=True)
    work = tempfile.mkdtemp(prefix="booth_", dir=base)
    clips, scores, weights, heard_bad = [], [], [], []
    try:
        for n, line in enumerate(lines):
            wav, score = _take(line, seed)
            if not wav:
                logger.warning(f"radio booth: {line['speaker']} could not say a line of {seg.key}")
                return None
            path = os.path.join(work, f"{n:02d}.wav")
            with open(path, "wb") as f:
                f.write(wav)
            nxt = lines[n + 1] if n + 1 < len(lines) else None
            clips.append((path, "phone" if is_caller(line["speaker"]) else "studio", _gap(line, nxt)))
            if score is not None:
                scores.append(score)
                weights.append(max(1, len(line["text"].split())))
                if score < qa.MIN_LINE:
                    heard_bad.append(n)

        match = round(sum(s * w for s, w in zip(scores, weights)) / sum(weights), 3) if scores else None
        if match is not None and match < qa.MIN_PIECE:
            logger.warning(f"radio booth: {seg.key} failed the round trip ({match})")
            return {"path": None, "qa": {"match": match, "bad_lines": heard_bad, "aired": False}}

        voice = os.path.join(work, "voice.wav")
        if not mix.join(clips, voice):
            return None
        recipe = seg.mix
        piece = out_mp3 if not (recipe == "sting" and sting) else os.path.join(work, "piece.mp3")
        if recipe in ("bed", "sting") and bed and os.path.exists(bed):
            ok = mix.over_bed(voice, bed, piece)
        elif recipe == "phone" and bed and os.path.exists(bed):
            # A phone-in sits on a very quiet bed: the line noise is the texture.
            ok = mix.over_bed(voice, bed, piece, bed_db=-16.0)
        else:
            ok = mix.plain(voice, piece)
        if ok and piece != out_mp3:
            ok = mix.after(sting, piece, out_mp3) if os.path.exists(sting) else os.replace(piece, out_mp3) is None
        if not ok:
            return None
        m = mix.measure(out_mp3)
        if not qa.levels_ok(m):
            logger.warning(f"radio booth: {seg.key} is outside the station's levels ({m})")
            return {"path": None, "qa": {"match": match, "levels": m, "aired": False}}
        return {"path": out_mp3, "seconds": (m or {}).get("seconds"),
                "qa": {"match": match, "bad_lines": heard_bad, "lufs": (m or {}).get("lufs"),
                       "peak": (m or {}).get("peak"), "aired": True}}
    finally:
        for f in os.listdir(work):
            try:
                os.unlink(os.path.join(work, f))
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass
