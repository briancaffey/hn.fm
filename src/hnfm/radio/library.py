"""What the station keeps in stock.

Two shelves. Episodes are the finished podcast MP3s the pipeline already
makes (`build_segment_episode`). The bank is the station's imaging and
music — spoken station IDs, sung jingles, and beds in each show's palette
— kept as MP3s under `outputs/radio/bank/` with one JSON manifest beside
them. What is written for one block does not live here: it lives with the
block (production.py), and the block's sheet names every file.
"""

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from . import radio_root

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Episodes
# ---------------------------------------------------------------------------


def episode_ref(item_id: int, run: int, seg: int) -> str:
    return f"{item_id}:{run}:{seg}"


def parse_ref(ref: str) -> Optional[tuple]:
    try:
        a, b, c = (int(x) for x in (ref or "").split(":"))
        return a, b, c
    except Exception:
        return None


def episodes(limit: int = 60) -> List[dict]:
    """Finished episodes whose MP3 is on disk, newest first.

    [{ref, item_id, run, seg, title, path, seconds, age_hours}]
    """
    from ..db import repo

    rows, _ = repo.list_episodes(offset=0, limit=limit * 2)
    out = []
    seen_items = set()
    for r in rows:
        path = r.get("episode_path")
        if not path or not os.path.exists(path):
            continue
        # One episode per story: a story re-rendered as runs 2, 3, 4 is the
        # same story three times, and the first fallback block aired it
        # four times in a row. Newest run wins (the rows are newest first).
        if r["item_id"] in seen_items:
            continue
        seen_items.add(r["item_id"])
        if len(out) >= limit:
            break
        created = r.get("created_at")
        age_h = None
        if created:
            try:
                age_h = round((datetime.utcnow() - datetime.fromisoformat(created.replace("Z", ""))).total_seconds() / 3600, 1)
            except Exception:
                age_h = None
        out.append({
            "ref": episode_ref(r["item_id"], r["run"], r["seg"]),
            "item_id": r["item_id"], "run": r["run"], "seg": r["seg"],
            "title": r.get("title") or f"Story {r['item_id']}",
            "path": path,
            "seconds": _duration(path),
            "age_hours": age_h,
        })
    return out


def episode(ref: str) -> Optional[dict]:
    """One episode by ref, looked up directly.

    Scanning `episodes()` for it probed every file on disk with ffprobe on
    every "what's next?" — a couple of seconds the DJ did not have, which
    showed up on air as a moment of the safety bed between items.
    """
    from ..db import repo

    parsed = parse_ref(ref)
    if not parsed:
        return None
    item_id, run, seg = parsed
    segment = repo.get_segment(item_id, run, seg)
    path = getattr(segment, "episode_path", None) if segment else None
    if not path or not os.path.exists(path):
        return None
    item = repo.get_item(item_id)
    return {
        "ref": ref, "item_id": item_id, "run": run, "seg": seg,
        "title": (item.title if item else None) or f"Story {item_id}",
        "path": path, "seconds": _duration(path), "age_hours": None,
    }


# ---------------------------------------------------------------------------
# The bank
# ---------------------------------------------------------------------------

BANK_DIR = "bank"
MANIFEST = "manifest.json"


def bank_dir() -> str:
    d = os.path.join(radio_root(), BANK_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _manifest_path() -> str:
    return os.path.join(bank_dir(), MANIFEST)


def load_bank() -> List[dict]:
    """[{id, kind, path, text, host, style, seconds, created_at, sheet_id?}]"""
    try:
        with open(_manifest_path()) as f:
            items = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [i for i in items if i.get("path") and os.path.exists(i["path"])]


def save_bank(items: List[dict]) -> None:
    tmp = _manifest_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(items, f, indent=1)
    os.replace(tmp, _manifest_path())


def add_to_bank(item: dict) -> dict:
    items = load_bank()
    item.setdefault("created_at", datetime.utcnow().isoformat())
    items.append(item)
    save_bank(items)
    return item


def bank_counts(show: Optional[str] = None) -> Dict[str, int]:
    """How much stock there is by kind, for the whole station or one show."""
    counts: Dict[str, int] = {}
    for i in load_bank():
        if show and i.get("show") != show:
            continue
        counts[i["kind"]] = counts.get(i["kind"], 0) + 1
    return counts


def pick_from_bank(kind: str, avoid_ids: List[str] = (), show: Optional[str] = None,
                   host: Optional[str] = None, strict: bool = False) -> Optional[dict]:
    """A stock item of `kind`: one made for `show` if there is one, the
    one that has waited longest among those not played lately, and — unless
    `strict` — whatever played longest ago when everything has played.
    With `strict`, nothing in `avoid_ids` is returned: the caller would
    rather skip than repeat."""
    items = [i for i in load_bank() if i["kind"] == kind]
    # The same sentence is the same item, whichever take it is.
    avoid = set(avoid_ids)
    if strict:
        said = {i.get("text") for i in items if i["id"] in avoid and i.get("text")}
        avoid |= {i["id"] for i in items if i.get("text") in said}
    pool = items
    if show and any(i.get("show") == show for i in items):
        pool = [i for i in items if i.get("show") == show]
    if host is not None and any(i.get("host") == host for i in pool):
        pool = [i for i in pool if i.get("host") == host]
    if not pool:
        return None
    fresh = [i for i in pool if i["id"] not in avoid]
    if fresh:
        return sorted(fresh, key=lambda i: i.get("created_at") or "")[0]
    if strict:
        return None
    order = list(avoid_ids)
    return max(pool, key=lambda i: order.index(i["id"]) if i["id"] in order else -1)


def safety_path() -> str:
    return os.path.join(radio_root(), "safety.mp3")


# ---------------------------------------------------------------------------
# ffmpeg helpers shared by voice, music and bank
# ---------------------------------------------------------------------------


# path -> (mtime, seconds). Episode files never change once written, so a
# probe is worth remembering for the life of the process.
_DURATIONS: Dict[str, tuple] = {}


def _duration(path: str) -> Optional[float]:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    hit = _DURATIONS.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        seconds = round(float(out), 1) if out else None
    except Exception:
        seconds = None
    _DURATIONS[path] = (mtime, seconds)
    return seconds


# Silence added to the end of everything the station makes, so items breathe
# instead of the next one arriving on the last syllable.
TAIL_PAD = float(os.getenv("RADIO_TAIL_PAD", "0.8"))


def to_mp3(src: str, dst: str, seconds: Optional[float] = None, fade: float = 1.5,
           loudnorm: bool = True, pad: Optional[float] = None) -> bool:
    """Any audio -> 128k MP3 at broadcast loudness, optionally trimmed with a
    fade out, with a moment of silence on the end. The station is one
    loudness everywhere; a quiet jingle after a loud episode is the tell of
    amateur radio, and a bed that starts on the host's last word is another."""
    filters = []
    if seconds:
        filters.append(f"atrim=0:{seconds}")
        filters.append(f"afade=t=out:st={max(0.0, seconds - fade)}:d={fade}")
    if loudnorm:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    pad = TAIL_PAD if pad is None else pad
    if pad:
        filters.append(f"apad=pad_dur={pad}")
    cmd = ["ffmpeg", "-y", "-i", src]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += ["-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "128k", dst]
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(dst):
        logger.warning(f"radio: mp3 encode failed: {res.stderr[-200:]}")
        return False
    return True
