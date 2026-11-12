"""A video of an edition: its cover, its words, its levels (issue #43).

One ffmpeg pass, no model and no browser. The show's cover fills the
frame, blurred, with the cover itself on the left; on the right are the
show, the edition, the chapter that is playing and the words as they are
spoken, and along the bottom the sound as a waveform. The words and their
timing come from the edition's own running order (the booth records when
each line starts), written out as an ASS subtitle file.

    edition_video(edition_id) -> path of the MP4, beside the edition's MP3
"""

import logging
import os
import subprocess
from typing import List, Optional

from . import archive, art

logger = logging.getLogger(__name__)

W, H, FPS = 1280, 720, 10
ORANGE = "&H006AFF&"   # ASS colours are blue-green-red
COLUMN = 560           # where the text column starts


def _t(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds // 3600)}:{int(seconds % 3600 // 60):02d}:{seconds % 60:05.2f}"


def _clean(text: str) -> str:
    return (text or "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _name(speaker: str) -> str:
    return f"LINE {speaker[6:]}" if speaker.startswith("caller") else speaker.upper()


def subtitles(e: dict) -> str:
    """The edition as an ASS file: a header that stays, the chapter that
    is playing, and each line for as long as it is spoken."""
    total = float(e.get("seconds") or 0) or sum(r.get("seconds") or 0 for r in e.get("rundown") or [])
    style = ("Style: {name},DejaVu Sans,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{bold},0,0,0,"
             "100,100,0,0,1,0,0,7,{left},70,{top},1")
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        style.format(name="Station", size=22, bold=-1, left=COLUMN, top=96),
        style.format(name="Show", size=54, bold=-1, left=COLUMN, top=126),
        style.format(name="Edition", size=24, bold=0, left=COLUMN, top=194),
        style.format(name="Chapter", size=24, bold=-1, left=COLUMN, top=262),
        style.format(name="Words", size=34, bold=0, left=COLUMN, top=306),
        style.format(name="Lyrics", size=24, bold=0, left=COLUMN, top=306),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def ev(start: float, end: float, st: str, text: str) -> str:
        return f"Dialogue: 0,{_t(start)},{_t(end)},{st},,0,0,0,,{text}"

    out: List[str] = [
        ev(0, total, "Station", f"{{\\c{ORANGE}}}H N F M"),
        ev(0, total, "Show", _clean(e.get("show_name") or "HNFM")),
        ev(0, total, "Edition", _clean(f"{e.get('title') or ''}  ·  {e.get('date') or ''}")),
    ]
    for r in e.get("rundown") or []:
        start, length = float(r.get("at") or 0), float(r.get("seconds") or 0)
        if length <= 0:
            continue
        spoken = bool(r.get("text"))
        label = (r.get("title") or r.get("name") or "") if spoken or r.get("lyrics") else "♪  " + (r.get("title") or "music")
        if len(label) > 58:
            label = label[:57].rstrip() + "…"
        out.append(ev(start, start + length, "Chapter", f"{{\\c{ORANGE}}}{_clean(label)}"))
        lines = r.get("text") or []
        cues = {c["n"]: c for c in (r.get("cues") or [])}
        if lines and not cues:
            # No recorded timing (an older edition): share the item out by words.
            words = [max(1, len(l["text"].split())) for l in lines]
            at = 1.0
            for n, wn in enumerate(words):
                d = (length - 2.0) * wn / sum(words)
                cues[n] = {"at": at, "seconds": d}
                at += d
        for n, l in enumerate(lines):
            c = cues.get(n)
            if not c:
                continue
            s0 = start + c["at"]
            nxt = cues.get(n + 1)
            s1 = start + nxt["at"] if nxt else min(start + length, s0 + c["seconds"] + 0.6)
            out.append(ev(s0, max(s1, s0 + 0.3), "Words",
                          f"{{\\c{ORANGE}\\fs20\\b1}}{_name(l['speaker'])}{{\\r}}\\N{_clean(l['text'])}"))
        if r.get("lyrics") and not lines[1:]:
            body = "\\N".join(x for x in r["lyrics"].splitlines() if x.strip() and not x.strip().startswith("["))
            out.append(ev(start + 4, start + length, "Lyrics", _clean(body)[:900]))
    return "\n".join(head + out) + "\n"


def backdrop_graph() -> str:
    """The still behind everything: the cover blurred and darkened to fill
    the frame, with the cover itself on the left. Made once per video, so
    the blur is not computed again for every frame."""
    return (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=28,"
        f"colorchannelmixer=rr=0.3:gg=0.3:bb=0.3[bg];"
        f"[0:v]scale=420:420[art];[bg][art]overlay=70:110[out]"
    )


def graph(ass_path: str) -> str:
    """Inputs: 0 the backdrop (a still), 1 the edition's audio."""
    ass = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return (
        f"[1:a]aformat=channel_layouts=mono,showwaves=s={W}x80:mode=cline:rate={FPS}:scale=sqrt:"
        # Drawn white and tinted after: the filter's own colour option came
        # out green through the pixel format conversion.
        f"colors=white:draw=full,format=rgb24,colorchannelmixer=rr=1:gg=0.42:bb=0[wave];"
        f"[0:v][wave]overlay=0:{H - 80}:shortest=1[b];"
        f"[b]ass='{ass}'[out]"
    )


def edition_video(edition_id: str) -> Optional[str]:
    e = archive.edition(edition_id)
    if not e or not os.path.exists(e["path"]):
        return None
    cover = art.path(e.get("show") or "") or art.path("station")
    if not cover:
        cover = art.draw(e.get("show") or "station") or art.draw("station")
    if not cover:
        logger.warning("radio video: no cover art and the image model is away")
        return None
    out = e["path"][:-4] + ".mp4"
    ass = e["path"][:-4] + ".ass"
    with open(ass, "w") as f:
        f.write(subtitles(e))
    tmp = out + ".tmp.mp4"
    still = e["path"][:-4] + ".backdrop.png"
    made = subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", cover, "-filter_complex",
                           backdrop_graph(), "-map", "[out]", "-frames:v", "1", still],
                          capture_output=True, text=True)
    if made.returncode != 0 or not os.path.exists(still):
        logger.warning(f"radio video: no backdrop: {made.stderr[-300:]}")
        return None
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", still,
           "-i", e["path"], "-filter_complex", graph(ass), "-map", "[out]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "33", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", tmp]
    res = subprocess.run(cmd, capture_output=True, text=True)
    for scrap in (ass, still):
        try:
            os.unlink(scrap)
        except OSError:
            pass
    if res.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 10000:
        logger.warning(f"radio video failed (exit {res.returncode}): {res.stderr[-400:]}")
        return None
    os.replace(tmp, out)
    return out
