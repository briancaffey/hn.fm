"""How a piece is mixed: recipes as ffmpeg filter graphs (issue #31).

A recipe takes voice clips and returns one MP3 at the station's loudness.
The graphs are built as text by pure functions (`*_graph`), so a test can
read a graph without running ffmpeg, and a change to the station's sound
is a change to one function.

    join       voices in turn with a beat between; callers go down a phone line
    plain      a voice on its own
    over_bed   a voice over music that ducks under it and comes back after
    after      a sting (a sung ident, say), then the piece
"""

import logging
import os
import subprocess
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

RATE = 44100
# Broadcast loudness for everything the station makes.
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
# Silence on the end of every item, so the next one does not land on the
# last syllable.
TAIL_PAD = float(os.getenv("RADIO_TAIL_PAD", "0.8"))
# A telephone: the band a phone line carries, squashed, a little dirty.
PHONE = ("highpass=f=320,lowpass=f=3300,"
         "acompressor=threshold=0.08:ratio=6:attack=5:release=80:makeup=2,"
         "acrusher=bits=9:mix=0.25,volume=0.9")
MP3 = ["-ac", "2", "-ar", str(RATE), "-c:a", "libmp3lame", "-b:a", "128k"]


def join_graph(roles: Sequence[str], gaps_ms: Sequence[int]) -> str:
    """N voice clips into one track. `roles[i]` is "studio" or "phone";
    `gaps_ms[i]` is the silence after clip i."""
    parts, labels = [], []
    for i, role in enumerate(roles):
        chain = [f"aresample={RATE}", "aformat=channel_layouts=mono"]
        if role == "phone":
            chain.append(PHONE)
        gap = max(0, int(gaps_ms[i])) / 1000.0
        if gap:
            chain.append(f"apad=pad_dur={gap}")
        parts.append(f"[{i}:a]{','.join(chain)}[c{i}]")
        labels.append(f"[c{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(roles)}:v=0:a=1[out]")
    return ";".join(parts)


def over_bed_graph(lead: float = 1.4, tail: float = 2.2, bed_db: float = -9.0,
                   duck_ratio: float = 9.0) -> str:
    """Input 0 is the voice, input 1 the bed (looped by the caller).

    The bed opens at `bed_db`, is pushed down by a sidechain compressor
    keyed on the voice, comes back up in the pauses and after the last
    word, and fades out over the tail. The old mix held the bed at a fixed
    minus seventeen: inaudible under speech on a phone speaker, and no
    louder in the gaps where there was room for it.
    """
    lead_ms = int(lead * 1000)
    return (
        f"[0:a]aresample={RATE},aformat=channel_layouts=stereo,adelay={lead_ms}|{lead_ms},"
        f"apad=pad_dur={tail},asplit=2[v][key];"
        f"[1:a]aresample={RATE},aformat=channel_layouts=stereo,volume={bed_db}dB,afade=t=in:st=0:d=0.6[bed];"
        f"[bed][key]sidechaincompress=threshold=0.02:ratio={duck_ratio}:attack=15:release=450:makeup=1[duck];"
        f"[v][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix];"
        f"[mix]areverse,afade=t=in:st=0:d={min(tail, 1.8)},areverse,{LOUDNORM},apad=pad_dur={TAIL_PAD}[out]"
    )


def plain_graph() -> str:
    return f"[0:a]aresample={RATE},{LOUDNORM},apad=pad_dur={TAIL_PAD}[out]"


def after_graph(overlap: float = 0.0) -> str:
    """Input 0 is the sting, input 1 the piece (already mixed). The sting
    plays, then the piece; both are at station loudness already."""
    return (f"[0:a]aresample={RATE},aformat=channel_layouts=stereo[s];"
            f"[1:a]aresample={RATE},aformat=channel_layouts=stereo[p];"
            f"[s][p]concat=n=2:v=0:a=1[out]")


def _run(cmd: List[str], dst: str) -> bool:
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) < 1000:
        logger.warning(f"radio mix failed (exit {res.returncode}): {res.stderr[-300:]}")
        return False
    return True


def join(clips: Sequence[Tuple[str, str, int]], dst_wav: str) -> bool:
    """[(wav path, role, gap_ms after)] -> one mono WAV."""
    if not clips:
        return False
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error"]
    for path, _role, _gap in clips:
        cmd += ["-i", path]
    cmd += ["-filter_complex", join_graph([c[1] for c in clips], [c[2] for c in clips]),
            "-map", "[out]", "-ar", str(RATE), dst_wav]
    return _run(cmd, dst_wav)


def plain(voice: str, dst: str) -> bool:
    return _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", voice, "-filter_complex", plain_graph(),
                 "-map", "[out]", *MP3, dst], dst)


def over_bed(voice: str, bed: str, dst: str, **kw) -> bool:
    return _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", voice, "-stream_loop", "-1", "-i", bed,
                 "-filter_complex", over_bed_graph(**kw), "-map", "[out]", *MP3, dst], dst)


def after(sting: str, piece: str, dst: str) -> bool:
    return _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", sting, "-i", piece,
                 "-filter_complex", after_graph(), "-map", "[out]", *MP3, dst], dst)


def concat(paths: Sequence[str], dst: str) -> bool:
    """Finished station MP3s end to end, re-encoded once: the archive of a
    block. Stream copy would be cheaper, but the bank holds files from
    several encoders and a copy of mismatched frames clicks at the joins."""
    if not paths:
        return False
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error"]
    for p in paths:
        cmd += ["-i", p]
    graph = "".join(f"[{i}:a]aresample={RATE},aformat=channel_layouts=stereo[a{i}];" for i in range(len(paths)))
    graph += "".join(f"[a{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=0:a=1[out]"
    cmd += ["-filter_complex", graph, "-map", "[out]", *MP3, dst]
    return _run(cmd, dst)


def silence(dst: str, seconds: float = 15.0) -> bool:
    """A file of nothing, for the moment the station has nothing: better
    one quiet file than a DJ asking for a missing one every three seconds."""
    return _run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i",
                 f"anullsrc=r={RATE}:cl=stereo", "-t", str(seconds), *MP3, dst], dst)


def measure(path: str) -> Optional[dict]:
    """{seconds, lufs, peak} of a finished file, from ffmpeg's own meter."""
    import json
    import re

    res = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", path, "-af",
         "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    d = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
    if not m:
        return None
    try:
        stats = json.loads(m.group(0))
        seconds = (int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))) if d else None
        return {"seconds": round(seconds, 1) if seconds else None,
                "lufs": float(stats["input_i"]), "peak": float(stats["input_tp"])}
    except (ValueError, KeyError):
        return None
