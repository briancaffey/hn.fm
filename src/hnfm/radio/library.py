"""What the station can play (plans/20).

Two shelves. Episodes are the finished podcast MP3s the pipeline already
makes (`build_segment_episode`), so the radio never re-renders anything.
The bank is the station's own material — station IDs, time checks, music
beds, and the lines a producer wrote for a specific block — kept as MP3s
under `outputs/radio/bank/` with one JSON manifest beside them.
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

    rows, _ = repo.list_episodes(offset=0, limit=limit)
    out = []
    for r in rows:
        path = r.get("episode_path")
        if not path or not os.path.exists(path):
            continue
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
    for e in episodes(limit=400):
        if e["ref"] == ref:
            return e
    return None


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


def bank_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for i in load_bank():
        if i.get("sheet_id"):
            continue  # block-specific lines are not the generic stock
        counts[i["kind"]] = counts.get(i["kind"], 0) + 1
    return counts


def pick_from_bank(kind: str, avoid_ids: List[str] = (), sheet_id: Optional[str] = None,
                   host: Optional[str] = None) -> Optional[dict]:
    """A bank item of `kind`, preferring one written for this sheet, then any
    generic one not played recently."""
    items = load_bank()
    if sheet_id:
        for i in items:
            if i.get("sheet_id") == sheet_id and i["kind"] == kind and i["id"] not in avoid_ids:
                return i
    pool = [i for i in items if i["kind"] == kind and not i.get("sheet_id")
            and (host is None or i.get("host") == host)]
    if not pool and host is not None:
        pool = [i for i in items if i["kind"] == kind and not i.get("sheet_id")]
    fresh = [i for i in pool if i["id"] not in avoid_ids]
    pool = fresh or pool
    if not pool:
        return None
    # Least recently created first is a fine proxy for "not overplayed".
    return sorted(pool, key=lambda i: i.get("created_at") or "")[0]


def safety_path() -> str:
    return os.path.join(radio_root(), "safety.mp3")


# ---------------------------------------------------------------------------
# ffmpeg helpers shared by voice, music and bank
# ---------------------------------------------------------------------------


def _duration(path: str) -> Optional[float]:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        return round(float(out), 1) if out else None
    except Exception:
        return None


def to_mp3(src: str, dst: str, seconds: Optional[float] = None, fade: float = 1.5,
           loudnorm: bool = True) -> bool:
    """Any audio -> 128k MP3 at broadcast loudness, optionally trimmed with a
    fade out. The station is one loudness everywhere; a quiet jingle after a
    loud episode is the tell of amateur radio."""
    filters = []
    if seconds:
        filters.append(f"atrim=0:{seconds}")
        filters.append(f"afade=t=out:st={max(0.0, seconds - fade)}:d={fade}")
    if loudnorm:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
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
