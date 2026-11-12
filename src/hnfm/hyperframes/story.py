"""What a story video is made from: the brief.

A narrated segment already holds everything a video needs to be timed
against: the script by section, one audio file that is those sections end
to end, and what the recogniser heard with a time on every word. This
module turns that into one plain dictionary, the brief, which the kit
lays out and the author (Hermes) writes scenes from.

Nothing here calls a model.
"""

import json
import os
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

# Seconds of title card before the narration starts, and of sign-off after.
LEAD = 3.0
TAIL = 4.0
# A caption is a breath, not a sentence.
CAPTION_WORDS = 7

_SPEAKER = re.compile(r"^\s*\[(S\d)\]\s*")
_SPACES = re.compile(r"\s+")


def clean(text: str) -> str:
    """Section text as it should be read on screen: no speaker tag, no
    wrapping quotes, ordinary spaces and hyphens."""
    t = _SPEAKER.sub("", text or "")
    t = t.replace(" ", " ").replace(" ", " ").replace("‑", "-")
    t = _SPACES.sub(" ", t).strip()
    if len(t) > 1 and t[0] in "\"“" and t[-1] in "\"”":
        t = t[1:-1].strip()
    return t


def speaker_of(text: str) -> str:
    m = _SPEAKER.match(text or "")
    return m.group(1) if m else "S1"


def phrases(text: str, n: int = CAPTION_WORDS) -> List[str]:
    """Caption-sized pieces, broken at punctuation where there is some."""
    words = text.split()
    out, cur = [], []
    for w in words:
        cur.append(w)
        ends = w[-1:] in ".!?;:" or (w[-1:] == "," and len(cur) >= 4)
        if len(cur) >= n or (ends and len(cur) >= 3):
            out.append(" ".join(cur))
            cur = []
    if cur:
        if out and len(cur) < 3:
            out[-1] += " " + " ".join(cur)
        else:
            out.append(" ".join(cur))
    return out


def cues(text: str, start: float, end: float, heard: List[dict]) -> List[dict]:
    """Each phrase of a section with the time it is spoken.

    The script has the right words and the recogniser has the right times,
    and the two do not agree word for word ("64 GB" is heard as two or
    three words). A phrase that starts a fraction of the way through the
    script's words is taken to start at the same fraction of the way
    through the words heard inside the section's window."""
    parts = phrases(text)
    total = max(1, len(text.split()))
    inside = [w for w in heard if start - 0.05 <= float(w.get("start", 0)) < end]
    out, done = [], 0
    for p in parts:
        frac = done / total
        if inside:
            t = float(inside[min(len(inside) - 1, int(round(frac * len(inside))))]["start"])
        else:
            t = start + frac * (end - start)
        out.append({"t": round(max(start, min(t, end - 0.2)), 2), "text": p})
        done += len(p.split())
    for i, c in enumerate(out):
        nxt = out[i + 1]["t"] if i + 1 < len(out) else end
        c["d"] = round(max(0.3, nxt - c["t"]), 2)
    return out


def _load(path: str) -> Optional[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def brief(item_id: int, run: int, seg: int) -> Optional[Dict]:
    """The brief for one narrated segment, or None if it has no narration."""
    from ..db import repo

    segment = repo.get_segment(item_id, run, seg)
    if not segment or not segment.audio_combined_path or not os.path.exists(segment.audio_combined_path):
        return None
    item = repo.get_item(item_id)
    seg_dir = os.path.dirname(os.path.dirname(segment.audio_combined_path))
    run_dir = os.path.dirname(os.path.dirname(seg_dir))
    asr = _load(segment.asr_json_path or "") or {}
    heard = asr.get("words") or [w for s in asr.get("segments") or [] for w in s.get("words") or []]
    processed = _load(os.path.join(run_dir, "processed.json")) or {}
    script = (getattr(segment, "script_json", None) or {}).get("sections") or []
    by_index = {int(s.get("index") or 0): s for s in script}

    scenes, t = [], 0.0
    for n in repo.list_section_numbers(item_id, run, seg):
        sec = repo.get_section(item_id, run, seg, n)
        if not sec or not sec.duration_ms:
            continue
        seconds = sec.duration_ms / 1000.0
        text = clean(sec.text)
        still = os.path.join(seg_dir, "images", str(n), "image.png")
        scenes.append({
            "n": len(scenes) + 1,
            "section": n,
            "speaker": speaker_of(sec.text),
            "beat": (by_index.get(n) or {}).get("beat") or "",
            "text": text,
            "start": round(t, 2),
            "seconds": round(seconds, 2),
            "cues": cues(text, t, t + seconds, heard),
            "image": still if os.path.exists(still) else None,
        })
        t += seconds
    if not scenes:
        return None

    url = (item.url if item else None) or f"https://news.ycombinator.com/item?id={item_id}"
    thumb = os.path.join(os.path.dirname(os.path.dirname(run_dir)), "thumb.jpg")
    return {
        "item_id": item_id, "run": run, "seg": seg,
        "title": (getattr(segment, "script_json", None) or {}).get("title") or (item.title if item else ""),
        "hn_title": item.title if item else "",
        "url": url,
        "domain": (urlparse(url).netloc or "").replace("www.", ""),
        "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
        "points": getattr(item, "score", None),
        "comments": getattr(item, "descendants", None),
        "summary": (processed.get("short_description") or processed.get("summary") or "")[:600],
        "theme": segment.style_theme or "default",
        "narration": {"path": segment.audio_combined_path, "seconds": round(t, 2)},
        "thumb": thumb if os.path.exists(thumb) else None,
        "lead": LEAD, "tail": TAIL,
        "seconds": round(LEAD + t + TAIL, 2),
        "scenes": scenes,
    }


def candidates(limit: int = 30) -> List[Dict]:
    """Narrated segments a video can be made from, newest first."""
    from sqlalchemy import text

    from ..db.engine import db_session

    with db_session() as s:
        rows = s.execute(text(
            "select s.item_id, s.run, s.seg, i.title, s.created_at, s.sections_total "
            "from segments s join hn_items i on i.id = s.item_id "
            "where s.audio_ready and s.audio_combined_path is not null "
            "order by s.created_at desc limit :n"), {"n": limit}).fetchall()
    return [{"item_id": r[0], "run": r[1], "seg": r[2], "title": r[3],
             "made": r[4].isoformat() if r[4] else None, "sections": r[5]} for r in rows]
