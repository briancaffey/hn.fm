"""The booth: a written piece becomes a finished file (issues #31, #32).

Each line is spoken in its voice, checked by ear (the round trip in
qa.py) and spoken again if it came out wrong. The lines are joined with a
beat between turns, each voice treated for where it speaks from and the
segment's effects placed among them (fx.py), and the result is mixed by
the segment's recipe: plain, over a ducking bed, or after a sting.

    record(piece, seg, ...) -> {path, seconds, qa} or None
"""

import logging
import os
import tempfile
from typing import List, Optional

from . import mix, qa
from .segments import Segment
from . import fx
from .cast import role_of
from .voice import is_caller, speak

logger = logging.getLogger(__name__)

# The beat after a line, by who spoke and who is next.
GAP_SAME, GAP_TURN, GAP_PHONE = 220, 300, 420
# How long the bed plays before the first word (mix.over_bed_graph).
BED_LEAD = 1.4
# The beat after an effect.
GAP_FX = 140
# What is heard when the piece goes to someone who is not in the studio,
# and when it comes back.
ARRIVE = {"phone": ("ring", "pickup"), "field": ("static",)}
LEAVE = {"phone": ("hangup",), "field": ("static",)}


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


def _fx(names) -> list:
    """Effect clips for the join; one that cannot be made is left out."""
    out = []
    for name in names:
        p = fx.path(name)
        if p:
            out.append((p, "fx", GAP_FX))
    return out


def layout(lines: List[dict], seg: Segment) -> list:
    """Where the effects go, as a list of ("line", n, role) and ("fx", name)
    in playing order. Pure, so the sound of a segment can be tested
    without making any.

    The spec gives the intro, the effect between lines, the one before the
    last line, the outro and a treatment for the last line. The rest is
    where people are: the first time the piece goes to the phone it rings
    and is picked up, a correspondent arrives through static, and both
    leave the way they came once nobody on that line speaks again."""
    out = [("fx", name) for name in seg.intro]
    roles = [role_of(l["speaker"]) for l in lines]
    arrived = set()
    last = len(lines) - 1
    for n, line in enumerate(lines):
        role = roles[n]
        if n and seg.between and not (n == last and seg.before_last):
            out.append(("fx", seg.between))
        if n == last and n and seg.before_last:
            out.append(("fx", seg.before_last))
        if role in ARRIVE and role not in arrived:
            arrived.add(role)
            out += [("fx", name) for name in ARRIVE[role]]
        out.append(("line", n, seg.last_role if (n == last and seg.last_role and n) else role))
        if role in LEAVE and role not in roles[n + 1:]:
            out += [("fx", name) for name in LEAVE[role]]
    return out + [("fx", name) for name in seg.outro]


def _wav_seconds(path: str) -> float:
    import wave

    try:
        with wave.open(path) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def cues(clips: list, lines_at: dict, lead: float = 0.0) -> List[dict]:
    """When each line starts and how long it runs, in seconds from the
    start of the finished item: `clips` is the join list, `lines_at` maps
    a clip's position to its line number, `lead` is whatever plays before
    the voice track (the bed's lead-in, a sting). For captions and for
    the page that follows the words."""
    out, at = [], lead
    for pos, (path, role, gap_ms) in enumerate(clips):
        seconds = _wav_seconds(path)
        if role == "fineprint":
            seconds /= 1.32
        if pos in lines_at:
            out.append({"n": lines_at[pos], "at": round(at, 2), "seconds": round(seconds, 2)})
        at += seconds + gap_ms / 1000.0
    return out


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
    lines_at: dict = {}
    try:
        for step in layout(lines, seg):
            if step[0] == "fx":
                clips += _fx([step[1]])
                continue
            _, n, role = step
            line = lines[n]
            wav, score = _take(line, seed)
            if not wav:
                logger.warning(f"radio booth: {line['speaker']} could not say a line of {seg.key}")
                return None
            path = os.path.join(work, f"{n:02d}.wav")
            with open(path, "wb") as f:
                f.write(wav)
            nxt = lines[n + 1] if n + 1 < len(lines) else None
            lines_at[len(clips)] = n
            clips.append((path, role, _gap(line, nxt)))
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
        bedded = recipe in ("bed", "sting", "phone") and bed and os.path.exists(bed)
        lead = BED_LEAD if bedded else 0.0
        if recipe == "sting" and sting and os.path.exists(sting):
            from .library import _duration

            lead += _duration(sting) or 0.0
        timing = cues(clips, lines_at, lead)
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
        return {"path": out_mp3, "seconds": (m or {}).get("seconds"), "cues": timing,
                "qa": {"match": match, "bad_lines": heard_bad, "lufs": (m or {}).get("lufs"),
                       "peak": (m or {}).get("peak"), "aired": True}}
    finally:
        for f in os.listdir(work):  # the effects live elsewhere and are kept
            try:
                os.unlink(os.path.join(work, f))
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass


def imaging(text: str, out_mp3: str, speaker: str = "announcer") -> Optional[str]:
    """A sweeper: a whoosh, the announcer's big voice, an impact. Made for
    the shelf, not for one block."""
    from . import radio_root

    wav = speak(text, speaker)
    if not wav:
        return None
    base = os.path.join(radio_root(), "tmp")
    os.makedirs(base, exist_ok=True)
    work = tempfile.mkdtemp(prefix="imaging_", dir=base)
    voice, joined = os.path.join(work, "v.wav"), os.path.join(work, "j.wav")
    try:
        with open(voice, "wb") as f:
            f.write(wav)
        clips = _fx(["whoosh"]) + [(voice, role_of(speaker), 60)] + _fx(["impact"])
        return out_mp3 if mix.join(clips, joined) and mix.plain(joined, out_mp3) else None
    finally:
        for f in (voice, joined):
            try:
                os.unlink(f)
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass
