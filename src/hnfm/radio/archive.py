"""The archive: every finished block, kept as one file (issue #35).

A stream is gone once it has played. Each block is also joined into a
single MP3 with a JSON sidecar — the running order, the words, the stories
— so the station's output can be listened to later, linked to, and offered
as a podcast feed.

Layout: outputs/radio/archive/YYYY-MM-DD/HHMM-<show>-<sheet>.{mp3,json}
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Optional

from . import mix, radio_root
from .format import show as show_by_key, station_now

logger = logging.getLogger(__name__)


def archive_root() -> str:
    d = os.path.join(radio_root(), "archive")
    os.makedirs(d, exist_ok=True)
    return d


def render(sheet: dict, stats: Optional[dict] = None, now: Optional[datetime] = None,
           kind: str = "block") -> Optional[dict]:
    """Join produced items into one file. `kind` is "block" (one quarter)
    or "episode" (a whole hour of a show). None if there is not enough to
    call it a programme."""
    from .library import _duration

    items = [i for i in sheet["items"] if i.get("status") == "ready" and i.get("path")
             and os.path.exists(i["path"])]
    if sum(1 for i in items if i.get("text")) < 3:
        return None
    now = now or station_now()
    sh = show_by_key(sheet["items"][0]["show"])
    day = os.path.join(archive_root(), now.strftime("%Y-%m-%d"))
    os.makedirs(day, exist_ok=True)
    stem = f"{now.strftime('%H%M')}-{sh.key}-{sheet['sheet_id']}"
    mp3 = os.path.join(day, stem + ".mp3")
    if not mix.concat([i["path"] for i in items], mp3):
        return None
    m = mix.measure(mp3) or {}
    at, rundown = 0.0, []
    for i in items:
        # The file's own length, not the planned one: chapter marks are
        # only useful if they land on the chapter.
        seconds = _duration(i["path"]) or i.get("seconds") or 0
        rundown.append({
            "at": round(at, 1), "seconds": round(seconds, 1), "segment": i["segment"], "name": i.get("name"),
            "title": i.get("title"), "story": i.get("story"), "host": i.get("host"),
            "text": i.get("text"), "lyrics": i.get("lyrics"), "review": i.get("review"), "qa": i.get("qa"),
            "cues": i.get("cues"),
        })
        at += seconds
    seen, stories = set(), []
    for i in items:
        if i.get("story") and i["story"] not in seen and i["segment"] != "cold_open":
            seen.add(i["story"])
            stories.append({"item_id": i["story"], "title": i.get("title")})
    meta = {
        "id": stem, "kind": kind, "sheet_id": sheet["sheet_id"], "title": sheet.get("title"), "show": sh.key,
        "show_name": sh.name, "anchor": sh.anchor, "cohost": sh.cohost, "tagline": sh.tagline,
        "date": now.strftime("%Y-%m-%d"), "aired_at": now.isoformat(), "seconds": m.get("seconds"),
        "stories": stories, "stats": stats or {}, "rundown": rundown,
    }
    with open(os.path.join(day, stem + ".json"), "w") as f:
        json.dump(meta, f)
    return meta


def _sidecar(edition_id: str) -> Optional[str]:
    safe = os.path.basename(edition_id)
    root = archive_root()
    for day in os.listdir(root):
        p = os.path.join(root, day, safe + ".json")
        if os.path.exists(p):
            return p
    return None


def update(edition_id: str, **fields) -> Optional[dict]:
    """Change what the desk may change about an edition: whether it is
    featured, and its title."""
    p = _sidecar(edition_id)
    if not p:
        return None
    with open(p) as f:
        meta = json.load(f)
    for k in ("featured", "title"):
        if k in fields and fields[k] is not None:
            meta[k] = fields[k]
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f)
    os.replace(tmp, p)
    meta.pop("rundown", None)
    return meta


def remove(edition_id: str) -> bool:
    """Take an edition out of the archive: its file, its sidecar and any
    video made of it."""
    p = _sidecar(edition_id)
    if not p:
        return False
    for ext in (".json", ".mp3", ".mp4"):
        try:
            os.unlink(p[:-5] + ext)
        except OSError:
            pass
    return True


def chapters(edition_id: str) -> Optional[dict]:
    """The running order as podcast chapters (the Podcasting 2.0 JSON
    format): the spoken items only, each at the second it starts."""
    e = edition(edition_id)
    if not e:
        return None
    out = [{"startTime": int(r["at"]), "title": (r.get("title") or r.get("name") or "")[:120]}
           for r in e.get("rundown") or [] if r.get("text") or r.get("lyrics")]
    return {"version": "1.2.0", "chapters": out}


def transcript(edition_id: str) -> Optional[str]:
    """The words of an edition as plain text, with the time of each item."""
    e = edition(edition_id)
    if not e:
        return None
    out = [f"{e.get('show_name')}: {e.get('title') or ''}", e.get("date") or "", ""]
    for r in e.get("rundown") or []:
        if not (r.get("text") or r.get("lyrics")):
            continue
        at = int(r["at"])
        out.append(f"[{at // 60}:{at % 60:02d}] {r.get('title') or r.get('name') or ''}")
        for l in r.get("text") or []:
            out.append(f"{l['speaker'].upper()}: {l['text']}")
        if r.get("lyrics"):
            out.append(r["lyrics"])
        out.append("")
    return "\n".join(out)


def editions(limit: int = 50) -> List[dict]:
    """Archived blocks, newest first, without their running orders."""
    out = []
    root = archive_root()
    for day in sorted(os.listdir(root), reverse=True):
        d = os.path.join(root, day)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d), reverse=True):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(d, name)) as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                continue
            meta.pop("rundown", None)
            meta["video"] = os.path.exists(os.path.join(d, name[:-5] + ".mp4"))
            out.append(meta)
            if len(out) >= limit:
                return out
    return out


def edition(edition_id: str) -> Optional[dict]:
    """One archived block with its running order, and where its file is."""
    safe = os.path.basename(edition_id)
    root = archive_root()
    for day in os.listdir(root):
        p = os.path.join(root, day, safe + ".json")
        if os.path.exists(p):
            with open(p) as f:
                meta = json.load(f)
            meta["path"] = os.path.join(root, day, safe + ".mp3")
            video = os.path.join(root, day, safe + ".mp4")
            meta["video_path"] = video if os.path.exists(video) else None
            return meta
    return None


def feed(base_url: str, limit: int = 50) -> str:
    """The archive as a podcast feed."""
    from email.utils import format_datetime
    from xml.sax.saxutils import escape

    base = base_url.rstrip("/")
    items = []
    for e in editions(limit):
        try:
            when = format_datetime(datetime.fromisoformat(e["aired_at"]))
        except Exception:
            when = ""
        stories = "; ".join(s["title"] for s in e.get("stories") or [] if s.get("title"))[:900]
        url = f"{base}/api/radio/archive/{e['id']}.mp3"
        items.append(
            f"<item><title>{escape(e.get('show_name') or 'HNFM')}: {escape(e.get('title') or '')}</title>"
            f"<guid isPermaLink=\"false\">{escape(e['id'])}</guid><pubDate>{when}</pubDate>"
            f"<description>{escape(stories)}</description>"
            f"<enclosure url=\"{escape(url)}\" type=\"audio/mpeg\" length=\"0\"/>"
            f"<itunes:image href=\"{escape(base)}/api/radio/art/{escape(e.get('show') or 'station')}.jpg\"/>"
            f"<podcast:chapters url=\"{escape(base)}/api/radio/archive/{escape(e['id'])}/chapters.json\" "
            f"type=\"application/json+chapters\"/>"
            f"<itunes:duration>{int(e.get('seconds') or 0)}</itunes:duration></item>")
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<rss version=\"2.0\" xmlns:itunes=\"http://www.itunes.com/dtds/podcast-1.0.dtd\" "
            "xmlns:podcast=\"https://podcastindex.org/namespace/1.0\"><channel>"
            f"<itunes:image href=\"{escape(base)}/api/radio/art/station.jpg\"/>"
            "<title>HNFM</title><description>Hacker News on the radio, made by local models. "
            "Every block the station airs, kept.</description>"
            f"<link>{escape(base)}/listen</link><language>en</language>"
            + "".join(items) + "</channel></rss>")
