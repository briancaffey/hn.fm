"""The director: what plays next, and what just played (plans/20).

Liquidsoap asks `next_item()` a few seconds before each track ends. The
answer comes from the current run sheet (see producer.py), unless a person
has queued something. When the sheet runs low a new block is planned in
the background, so the air never waits on the model; if there is no sheet
at all, the deterministic fallback plans one on the spot.

Every track change Liquidsoap reports lands in `radio_events`, which is
the station's history and the Live page's feed.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from . import radio_root
from .library import episode, episodes, pick_from_bank, parse_ref, safety_path

logger = logging.getLogger(__name__)

BLOCK_MINUTES = int(os.getenv("RADIO_BLOCK_MINUTES", "30"))
# Plan the next block when this many items remain on the current one.
REPLAN_AT = 3
# Don't re-air an episode within this window.
NO_REPEAT_HOURS = int(os.getenv("RADIO_NO_REPEAT_HOURS", "3"))
SETTING_QUEUE = "radio.queue"
SETTING_PLANNING = "radio.planning_since"


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


def current_sheet() -> Optional[dict]:
    from ..db import repo

    return repo.radio_current_sheet()


def plan_now(minutes: int = None, reason: str = "manual") -> dict:
    """Plan a block synchronously (the task and the API both call this)."""
    from ..db import repo
    from .producer import plan_block

    minutes = minutes or BLOCK_MINUTES
    recent = repo.radio_recent_events(hours=NO_REPEAT_HOURS)
    eps = episodes(limit=80)
    sheet, source, usage = plan_block(eps, recent, minutes)
    row = repo.radio_save_sheet(
        sheet_id=uuid.uuid4().hex[:12], title=sheet.title, minutes=minutes,
        items=[i.model_dump() for i in sheet.items], source=source,
        model=usage.get("model"), tokens_in=usage.get("tokens_in", 0),
        tokens_out=usage.get("tokens_out", 0), reason=reason,
    )
    repo.set_setting(SETTING_PLANNING, None)
    logger.info(
        f"📻 planned block {row['sheet_id']} ({source}): {len(sheet.items)} items, "
        f"{usage.get('tokens_in', 0)}/{usage.get('tokens_out', 0)} tokens — {sheet.title}"
    )
    return row


def _request_plan() -> None:
    """Ask for a new block in the background, at most once at a time."""
    from ..db import repo

    since = repo.get_setting(SETTING_PLANNING)
    if since:
        try:
            if datetime.utcnow() - datetime.fromisoformat(since) < timedelta(minutes=5):
                return
        except Exception:
            pass
    repo.set_setting(SETTING_PLANNING, datetime.utcnow().isoformat())
    try:
        from ..web.tasks import radio_plan_block

        radio_plan_block.apply_async(kwargs={"reason": "sheet low"})
    except Exception as e:
        logger.warning(f"radio: could not dispatch a plan ({e}); planning inline")
        plan_now(reason="sheet low (inline)")


# ---------------------------------------------------------------------------
# The queue: a person said "play this next"
# ---------------------------------------------------------------------------


def queue() -> List[str]:
    from ..db import repo

    return list(repo.get_setting(SETTING_QUEUE, []) or [])


def enqueue(ref: str) -> List[str]:
    from ..db import repo

    if not episode(ref):
        raise ValueError(f"no finished episode {ref}")
    q = [r for r in queue() if r != ref] + [ref]
    repo.set_setting(SETTING_QUEUE, q)
    return q


def _pop_queue() -> Optional[str]:
    from ..db import repo

    q = queue()
    if not q:
        return None
    ref, rest = q[0], q[1:]
    repo.set_setting(SETTING_QUEUE, rest)
    return ref


# ---------------------------------------------------------------------------
# Next
# ---------------------------------------------------------------------------


def _resolve(item: dict, sheet_id: str, recent_ids: List[str]) -> Optional[dict]:
    """A run-sheet item -> what Liquidsoap needs: a path and metadata."""
    kind = item.get("kind")
    if kind == "episode":
        e = episode(item.get("episode") or "")
        if not e:
            return None
        return {"kind": kind, "path": e["path"], "title": e["title"], "ref": e["ref"],
                "item_id": e["item_id"], "run": e["run"], "seg": e["seg"],
                "seconds": e.get("seconds")}
    if kind == "music":
        b = pick_from_bank("music", avoid_ids=recent_ids, sheet_id=sheet_id)
        if not b:
            return None
        return {"kind": kind, "path": b["path"], "title": b.get("style") or "music",
                "bank_id": b["id"], "seconds": b.get("seconds")}
    # A spoken line: the one written for this block if it was voiced in
    # time, otherwise a generic station ID in the same host's voice.
    b = pick_from_bank(kind, avoid_ids=recent_ids, sheet_id=sheet_id, host=item.get("host"))
    if not b and kind != "station_id":
        b = pick_from_bank("station_id", avoid_ids=recent_ids, host=item.get("host"))
    if not b:
        return None
    return {"kind": kind, "path": b["path"], "title": b.get("text") or kind,
            "host": b.get("host"), "bank_id": b["id"]}


def next_item() -> dict:
    """What Liquidsoap should play next. Always answers something."""
    from ..db import repo

    recent = repo.radio_recent_events(hours=1)
    recent_ids = [r.get("meta", {}).get("bank_id") for r in recent if r.get("meta", {}).get("bank_id")]

    queued = _pop_queue()
    if queued:
        e = episode(queued)
        if e:
            return {"kind": "episode", "path": e["path"], "title": e["title"], "ref": e["ref"],
                    "item_id": e["item_id"], "run": e["run"], "seg": e["seg"], "queued": True}

    sheet = current_sheet()
    if not sheet:
        sheet = plan_now(reason="no sheet")
        _request_plan()

    for _ in range(len(sheet["items"]) + 1):
        idx = sheet["cursor"]
        if idx >= len(sheet["items"]):
            break
        item = sheet["items"][idx]
        repo.radio_advance_sheet(sheet["sheet_id"])
        sheet["cursor"] = idx + 1
        resolved = _resolve(item, sheet["sheet_id"], recent_ids)
        if len(sheet["items"]) - sheet["cursor"] <= REPLAN_AT:
            _request_plan()
        if resolved:
            resolved["sheet_id"] = sheet["sheet_id"]
            return resolved
        logger.info(f"radio: item {idx} ({item.get('kind')}) unavailable, skipping")

    # Sheet exhausted before a replacement arrived: plan one now, inline.
    sheet = plan_now(reason="exhausted")
    return next_item() if sheet["items"] else _safety()


def _safety() -> dict:
    p = safety_path()
    if not os.path.exists(p):
        beds = [b for b in __import__("hnfm.radio.library", fromlist=["load_bank"]).load_bank()
                if b["kind"] == "music"]
        p = beds[0]["path"] if beds else p
    return {"kind": "music", "path": p, "title": "HNFM", "safety": True}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def record_event(meta: dict) -> dict:
    """Liquidsoap's on_track callback: the metadata of what just started."""
    from ..db import repo

    kind = meta.get("hnfm_kind") or "unknown"
    title = meta.get("title") or meta.get("filename") or ""
    ref = meta.get("hnfm_ref") or None
    keep = {k: v for k, v in meta.items() if k in (
        "hnfm_kind", "hnfm_ref", "hnfm_host", "hnfm_bank_id", "hnfm_sheet", "filename", "title")}
    if keep.get("hnfm_bank_id"):
        keep["bank_id"] = keep.pop("hnfm_bank_id")
    return repo.radio_record_event(kind=kind, title=title, ref=ref, meta=keep)


def now_playing() -> Optional[dict]:
    from ..db import repo

    ev = repo.radio_recent_events(hours=6, limit=1)
    if not ev:
        return None
    e = ev[-1]
    if e.get("ref"):
        parsed = parse_ref(e["ref"])
        if parsed:
            e["item_id"], e["run"], e["seg"] = parsed
    return e


def status() -> dict:
    """Everything the page and the monitor want in one call."""
    from ..db import repo
    from .library import bank_counts

    sheet = current_sheet()
    return {
        "enabled": True,
        "now": now_playing(),
        "queue": queue(),
        "sheet": None if not sheet else {
            "sheet_id": sheet["sheet_id"], "title": sheet["title"],
            "source": sheet["source"], "cursor": sheet["cursor"],
            "items": len(sheet["items"]), "created_at": sheet["created_at"],
        },
        "bank": bank_counts(),
        "episodes": len(episodes(limit=200)),
        "icecast": icecast_status(),
        "root": radio_root(),
    }


def icecast_status() -> dict:
    """Listeners and mounts from Icecast's status JSON, or why not."""
    import requests

    base = os.getenv("ICECAST_BASE_URL", "http://icecast:8000").rstrip("/")
    try:
        r = requests.get(f"{base}/status-json.xsl", timeout=5)
        d = (r.json() or {}).get("icestats") or {}
    except Exception as e:
        return {"up": False, "error": str(e)[:120]}
    src = d.get("source") or []
    if isinstance(src, dict):
        src = [src]
    return {
        "up": True,
        "server_start": d.get("server_start_iso8601"),
        "mounts": [{
            "mount": (s.get("listenurl") or "").rsplit("/", 1)[-1],
            "listeners": s.get("listeners", 0),
            "peak": s.get("listener_peak", 0),
            "title": s.get("title"),
            "bitrate": s.get("bitrate"),
        } for s in src],
    }
