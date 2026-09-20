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

from . import log, radio_root
from .library import episode, episodes, pick_from_bank, parse_ref, safety_path

logger = logging.getLogger(__name__)

BLOCK_MINUTES = int(os.getenv("RADIO_BLOCK_MINUTES", "30"))
# Plan the next block when this many items remain on the current one.
REPLAN_AT = 3
# Don't re-air an episode within this window.
# Once a story has aired it is done: a week is "never" for news.
NO_REPEAT_HOURS = int(os.getenv("RADIO_NO_REPEAT_HOURS", str(24 * 7)))
# A generic line (station ID) is not repeated within this window; the
# director skips it rather than say the same sentence twice in an hour.
ID_WINDOW_HOURS = 1
SETTING_QUEUE = "radio.queue"
SETTING_PLANNING = "radio.planning_since"


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


def current_sheet() -> Optional[dict]:
    from ..db import repo

    return repo.radio_current_sheet()


def plan_now(minutes: int = None, reason: str = "manual") -> dict:
    """Plan a block synchronously. The plan task calls this and then voices
    the block; nothing else should, because an unvoiced block airs as
    skips. The director never plans inline any more: while it waits for
    the task it holds on music (`_hold`).
    """
    from ..db import repo
    from .briefs import candidates
    from .producer import plan_block

    minutes = minutes or BLOCK_MINUTES
    recent = repo.radio_recent_events(hours=NO_REPEAT_HOURS)
    eps = episodes(limit=80)
    stories = candidates(limit=40)
    # What is already on the belt: the unserved tail of every open sheet.
    # Two blocks planned minutes apart used to open on the same stories.
    planned = []
    for sh in repo.radio_list_sheets(limit=4):
        planned.extend(sh["items"][sh["cursor"]:])
    sheet, source, usage = plan_block(eps, stories, recent, planned, minutes)
    # A block with lines to voice is parked until the task has voiced them
    # (`radio_mark_ready`); a hold of beds has nothing to wait for.
    spoken = any(i.kind not in ("music", "episode") for i in sheet.items)
    row = repo.radio_save_sheet(
        sheet_id=uuid.uuid4().hex[:12], title=sheet.title, minutes=minutes,
        items=[i.model_dump() for i in sheet.items], source=source,
        model=usage.get("model"), tokens_in=usage.get("tokens_in", 0),
        tokens_out=usage.get("tokens_out", 0), reason=reason, ready=not spoken,
    )
    repo.set_setting(SETTING_PLANNING, None)
    logger.info(
        f"📻 planned block {row['sheet_id']} ({source}): {len(sheet.items)} items, "
        f"{usage.get('tokens_in', 0)}/{usage.get('tokens_out', 0)} tokens — {sheet.title}"
    )
    log("producer",
        f"planned a {minutes}-minute block, {len(sheet.items)} items"
        + (f" ({usage.get('tokens_in', 0)} in / {usage.get('tokens_out', 0)} out tokens)"
           if source == "llm" else " with the deterministic producer"),
        sheet_id=row["sheet_id"], source=source, items=len(sheet.items), reason=reason)
    return row


PLAN_WINDOW = timedelta(minutes=5)


def planning_since() -> Optional[datetime]:
    """When a model plan was last requested and has not landed yet, if within the window."""
    from ..db import repo

    since = repo.get_setting(SETTING_PLANNING)
    if not since:
        return None
    try:
        at = datetime.fromisoformat(since)
    except Exception:
        return None
    return at if datetime.utcnow() - at < PLAN_WINDOW else None


def request_plan(reason: str = "sheet low", minutes: int = None, force: bool = False) -> dict:
    """Ask for a new block in the background, at most one in flight.

    Every caller — the director when a sheet runs low, the monitor, the
    manual button — comes through here, so two of them within the window
    produce one task. `force` is the manual button's "I mean it".
    """
    from ..db import repo

    since = planning_since()
    if since and not force:
        return {"status": "already planning", "since": since.isoformat()}
    repo.set_setting(SETTING_PLANNING, datetime.utcnow().isoformat())
    log("director", f"asked the producer for the next block ({reason})")
    try:
        from ..web.tasks import radio_plan_block

        t = radio_plan_block.apply_async(kwargs={"reason": reason, "minutes": minutes})
        return {"status": "queued", "task_id": t.id}
    except Exception as e:
        logger.warning(f"radio: could not dispatch a plan ({e}); planning inline")
        row = plan_now(reason=f"{reason} (inline)")
        repo.radio_mark_ready(row["sheet_id"])  # nobody will voice it; air what the bank has
        return {"status": "planned", "sheet_id": row["sheet_id"]}


def _request_plan() -> None:
    request_plan()


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
    log("director", f"someone queued {ref} to play next", ref=ref)
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
    if kind in ("brief", "feature", "bit"):
        # Written and voiced for this block by the bank; there is no generic
        # substitute for a story or a bit, so a missing one is skipped.
        from .library import load_bank

        b = next((x for x in load_bank()
                  if x.get("sheet_id") == sheet_id and x.get("kind") == kind
                  and (kind == "bit" and x.get("bit") == item.get("bit")
                       or kind != "bit" and x.get("story") == item.get("story"))), None)
        if not b:
            return None
        out = {"kind": kind, "path": b["path"], "title": b.get("text") or kind,
               "host": b.get("host"), "bank_id": b["id"]}
        if b.get("story"):
            out["ref"] = f"story:{b['story']}"
            out["item_id"] = b["story"]
        return out
    # A spoken line: the one written for this block, if it was voiced in
    # time. A time check or coming-up line that was not voiced is skipped —
    # it used to become a station ID, which is how a block of nothing
    # aired as the same two IDs over and over. A station ID is never
    # repeated within the hour; the director would rather say nothing.
    b = pick_from_bank(kind, avoid_ids=recent_ids, sheet_id=sheet_id, host=item.get("host"),
                       strict=(kind == "station_id"))
    if not b:
        return None
    return {"kind": kind, "path": b["path"], "title": b.get("text") or kind,
            "host": b.get("host"), "bank_id": b["id"]}


def next_item() -> dict:
    """What Liquidsoap should play next. Always answers something."""
    from ..db import repo

    recent_ids = _recently_played(hours=ID_WINDOW_HOURS)

    log("dj", "asked what's next")
    queued = _pop_queue()
    if queued:
        e = episode(queued)
        if e:
            log("director", f"served the queued episode: {e['title'][:60]}", kind="episode", ref=e["ref"])
            return {"kind": "episode", "path": e["path"], "title": e["title"], "ref": e["ref"],
                    "item_id": e["item_id"], "run": e["run"], "seg": e["seg"], "queued": True}

    sheet = current_sheet()
    if not sheet:
        return _hold(recent_ids, "no block yet")

    for _ in range(len(sheet["items"]) + 1):
        idx = sheet["cursor"]
        if idx >= len(sheet["items"]):
            break
        item = sheet["items"][idx]
        repo.radio_advance_sheet(sheet["sheet_id"])
        sheet["cursor"] = idx + 1
        resolved = _resolve(item, sheet["sheet_id"], recent_ids)
        # Running low matters only when nothing is planned behind this block.
        if len(sheet["items"]) - sheet["cursor"] <= REPLAN_AT and len(repo.radio_open_sheets()) <= 1:
            _request_plan()
        if resolved:
            resolved["sheet_id"] = sheet["sheet_id"]
            log("director",
                f"served item {idx + 1}/{len(sheet['items'])}: {resolved['kind']} — {str(resolved.get('title'))[:60]}",
                kind=resolved["kind"], index=idx, of=len(sheet["items"]), sheet_id=sheet["sheet_id"],
                host=resolved.get("host"), bank_id=resolved.get("bank_id"))
            return resolved
        logger.info(f"radio: item {idx} ({item.get('kind')}) unavailable, skipping")
        log("director", f"item {idx + 1} ({item.get('kind')}) is not in the bank yet; skipped", kind=item.get("kind"))

    # Sheet exhausted before a replacement arrived: hold on music.
    return _hold(recent_ids, "block exhausted")


HOLD_FILL_SETTING = "radio.hold_fill_at"


def _recently_played(hours: int = 1) -> List[str]:
    """Bank ids played or handed out in the window, newest first.

    Two sources, because the DJ prefetches: its playback reports arrive a
    track or two after the director served the item, so a list built from
    reports alone let the same station ID be served twice a minute. What
    the director itself served in the window counts as played.
    """
    from ..db import repo

    cutoff = datetime.utcnow() - timedelta(hours=hours)
    seen, out = set(), []
    for r in repo.radio_recent_events(hours=hours):
        bid = (r.get("meta") or {}).get("bank_id")
        if bid and bid not in seen:
            seen.add(bid)
            out.append(bid)
    served = [r for r in repo.radio_log_tail(limit=300)
              if r.get("component") == "director" and (r.get("meta") or {}).get("bank_id")]
    for r in reversed(served):
        try:
            if datetime.fromisoformat(r["at"]) < cutoff:
                continue
        except Exception:
            pass
        bid = r["meta"]["bank_id"]
        if bid not in seen:
            seen.add(bid)
            out.append(bid)
    return out


def _hold(recent_ids: List[str], why: str) -> dict:
    """Music while the producer works: the bed that has waited longest,
    never a spoken line. Asks for a block (once), and for fresh beds when
    every bed has played this hour. This is the whole of what the station
    does with nothing to say — it does not build a block of station IDs.
    """
    from ..db import repo

    _request_plan()
    b = pick_from_bank("music", avoid_ids=recent_ids)
    if b and b["id"] in recent_ids:
        # Every bed has played within the hour: ask for new ones, at most
        # every ten minutes, and play the longest-ago meanwhile.
        last = repo.get_setting(HOLD_FILL_SETTING)
        try:
            stale = not last or datetime.utcnow() - datetime.fromisoformat(last) > timedelta(minutes=10)
        except Exception:
            stale = True
        if stale:
            repo.set_setting(HOLD_FILL_SETTING, datetime.utcnow().isoformat())
            try:
                from ..web.tasks import radio_fill_bank

                radio_fill_bank.apply_async(kwargs={"max_new": 2})
            except Exception as e:
                logger.debug(f"radio: could not ask for beds ({e})")
    if not b:
        return _safety()
    log("director", f"holding on music ({why}): {b.get('style') or 'bed'}", kind="music", hold=True,
        bank_id=b["id"])
    return {"kind": "music", "path": b["path"], "title": b.get("style") or "music",
            "bank_id": b["id"], "seconds": b.get("seconds"), "hold": True}


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

    kind = meta.get("hnfm_kind")
    if not kind:
        # Not one of ours: the safety bed, a blank, a crossfade's internal
        # track mark. The history is what the station chose to play.
        return {"ignored": True, "reason": "no hnfm_kind"}
    title = meta.get("title") or meta.get("filename") or ""
    ref = meta.get("hnfm_ref") or None
    keep = {k: v for k, v in meta.items() if k in (
        "hnfm_kind", "hnfm_ref", "hnfm_host", "hnfm_bank_id", "hnfm_sheet", "filename", "title")}
    if keep.get("hnfm_bank_id"):
        keep["bank_id"] = keep.pop("hnfm_bank_id")
    # Metadata can announce the same file twice within a moment (the
    # request, then the decoder); one play is one row.
    last = repo.radio_recent_events(hours=1, limit=1)
    if last:
        prev = last[-1]
        same = (prev.get("ref") or "") == (ref or "") and (prev.get("meta") or {}).get("bank_id") == keep.get("bank_id") \
            and prev.get("title") == title
        try:
            age = (datetime.utcnow() - datetime.fromisoformat(prev["at"])).total_seconds()
        except Exception:
            age = 999
        if same and age < 8:
            return {"ignored": True, "reason": "duplicate announcement"}
    log("dj", f"on air: {kind} — {title[:60]}", kind=kind, ref=ref, host=meta.get("hnfm_host") or None)
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
