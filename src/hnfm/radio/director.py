"""The director: what plays next, and what just played.

Liquidsoap asks `next_item()` a few seconds before each track ends. The
answer is the next item of the current block, which production has already
made: the sheet names every file, so serving is reading a row. When a
block runs low the next is asked for in the background; while there is
none the station holds on its library and never on a spoken loop.

The station does not produce for nobody (issue #33). With no listener it
plays music, idents and repeats from the shelf, and the models are left
alone. Someone tuning in wakes the producer.
"""

import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from . import log, radio_root
from .format import schedule, show_at, station_now
from .library import episode, episodes, parse_ref, pick_from_bank, safety_path

logger = logging.getLogger(__name__)

# A block is one quarter of the clock: about ten minutes of air.
BLOCK_MINUTES = int(os.getenv("RADIO_BLOCK_MINUTES", "15"))
# Ask for the next block when this many items remain on the current one.
REPLAN_AT = int(os.getenv("RADIO_REPLAN_AT", "5"))
# Once a story has aired it is done: a week is "never" for news.
NO_REPEAT_HOURS = int(os.getenv("RADIO_NO_REPEAT_HOURS", str(24 * 7)))
# Stock (a bed, an ident) is not repeated within this window.
STOCK_WINDOW_HOURS = 1
# After the last listener leaves, keep producing for this long: someone who
# pauses for a phone call should come back to a station still talking.
LINGER_MINUTES = int(os.getenv("RADIO_LINGER_MINUTES", "10"))
# Segments that are as good tomorrow: what the station repeats when idle.
EVERGREEN = ("sponsor", "joke", "sketch", "word", "stack")
SETTING_QUEUE = "radio.queue"
SETTING_PLANNING = "radio.planning_since"
SETTING_HEARD = "radio.last_listener_at"
SETTING_IDLE_N = "radio.idle_n"
SETTING_LAST_PLAN = "radio.last_plan"
PLAN_WINDOW = timedelta(minutes=15)


# ---------------------------------------------------------------------------
# Who is listening, and whether to make anything
# ---------------------------------------------------------------------------


MODES = ("listeners", "always", "off")
SETTING_PRODUCE = "radio.produce"


def produce_mode() -> str:
    """listeners: produce while someone is tuned in, and for the scheduled
    editions. always: produce around the clock. off: only when asked by
    hand. Set at the desk (a setting); the environment gives the default."""
    try:
        from ..db import repo

        chosen = repo.get_setting(SETTING_PRODUCE)
        if chosen in MODES:
            return chosen
    except Exception:
        pass
    mode = os.getenv("RADIO_PRODUCE", "listeners").strip().lower()
    return mode if mode in MODES else "listeners"


def set_produce_mode(mode: str) -> str:
    from ..db import repo

    if mode not in MODES:
        raise ValueError(f"mode is one of {', '.join(MODES)}")
    repo.set_setting(SETTING_PRODUCE, mode)
    log("director", f"production set to {mode} at the desk")
    return mode


_LISTENERS = {"at": 0.0, "n": 0}


def listeners() -> int:
    """How many are tuned in, asked of the transmitter at most every
    fifteen seconds. The DJ itself is not a listener."""
    from ..db import repo

    if time.time() - _LISTENERS["at"] < 15:
        return _LISTENERS["n"]
    st = icecast_status(timeout=2)
    n = sum(m.get("listeners", 0) for m in (st.get("mounts") or [])) if st.get("up") else 0
    _LISTENERS.update(at=time.time(), n=n)
    if n:
        repo.set_setting(SETTING_HEARD, datetime.utcnow().isoformat())
    return n


def audience() -> dict:
    from ..db import repo

    n = listeners()
    heard = repo.get_setting(SETTING_HEARD)
    recent = False
    if heard:
        try:
            recent = datetime.utcnow() - datetime.fromisoformat(heard) < timedelta(minutes=LINGER_MINUTES)
        except Exception:
            recent = False
    return {"listeners": n, "last_listener_at": heard, "present": bool(n) or recent}


def should_produce() -> bool:
    mode = produce_mode()
    if mode == "always":
        return True
    if mode == "off":
        return False
    return audience()["present"]


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


def current_sheet() -> Optional[dict]:
    from ..db import repo

    return repo.radio_current_sheet()


def _used() -> tuple:
    """(story ids, titles) that aired this week or are already planned."""
    from ..db import repo

    ids, titles = set(), []
    for r in repo.radio_recent_events(hours=NO_REPEAT_HOURS, limit=2000):
        ref = str(r.get("ref") or "")
        if ref.startswith("story:"):
            try:
                ids.add(int(ref[6:]))
            except ValueError:
                pass
            titles.append(r.get("title") or "")
    # Every block made in the window, aired or not: an edition made for the
    # archive never airs, and its stories are just as used.
    cutoff = (datetime.utcnow() - timedelta(hours=NO_REPEAT_HOURS)).isoformat()
    for sh in repo.radio_list_sheets(limit=400):
        if (sh.get("created_at") or "") < cutoff:
            continue
        for it in sh["items"]:
            if it.get("story"):
                ids.add(int(it["story"]))
                titles.append(it.get("title") or "")
    return ids, titles


def plan_now(minutes: int = None, reason: str = "manual", at: Optional[datetime] = None,
             quarter: Optional[int] = None) -> Optional[dict]:
    """Plan a block and park it. The plan task calls this and then makes
    the block (production.produce); nothing else should, because a block
    that is planned and not made airs as skips. None if there is nothing
    new to say.

    `at` and `quarter` plan a block for another hour of the day: an
    edition for the archive, which does not move the on-air sequence."""
    from ..db import repo
    from .planner import plan

    from .format import hour_key, next_quarter

    now = at or station_now()
    live = quarter is None
    if live:
        quarter = next_quarter(repo.get_setting(SETTING_LAST_PLAN), now)
    ids, titles = _used()
    p = plan(now, quarter, used_stories=ids, used_titles=titles)
    if not p["stories"]:
        log("producer", "nothing new to say; staying on the library", reason=reason)
        return None
    if live:
        repo.set_setting(SETTING_LAST_PLAN, {"hour": hour_key(now), "quarter": quarter})
    minutes = minutes or BLOCK_MINUTES
    usage = p.get("usage") or {}
    row = repo.radio_save_sheet(
        sheet_id=uuid.uuid4().hex[:12], title=p["title"], minutes=minutes, items=p["items"],
        source=p["source"], model=usage.get("model"), tokens_in=usage.get("tokens_in", 0),
        tokens_out=usage.get("tokens_out", 0), reason=reason, ready=False,
    )
    logger.info(f"📻 planned block {row['sheet_id']} ({p['source']}): {len(p['items'])} items — {p['title']}")
    return row


def planning_since() -> Optional[datetime]:
    """When a block was last asked for and has not landed yet, if recent."""
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
    button — comes through here. `force` is a person saying "I mean it":
    it skips both the one-in-flight rule and the nobody-is-listening rule.
    """
    from ..db import repo

    if not force and not should_produce():
        return {"status": "idle", "why": "nobody is listening"}
    since = planning_since()
    if since and not force:
        return {"status": "already planning", "since": since.isoformat()}
    parked = repo.radio_parked_sheets()
    if parked and not force:
        return {"status": "already planning", "parked": parked[0]["sheet_id"]}
    repo.set_setting(SETTING_PLANNING, datetime.utcnow().isoformat())
    log("director", f"asked the producer for the next block ({reason})")
    try:
        from ..web.tasks import radio_plan_block

        t = radio_plan_block.apply_async(kwargs={"reason": reason, "minutes": minutes})
        return {"status": "queued", "task_id": t.id}
    except Exception as e:
        repo.set_setting(SETTING_PLANNING, None)
        logger.warning(f"radio: could not dispatch a plan ({e})")
        return {"status": "error", "error": str(e)[:120]}


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


def _serve(item: dict, sheet_id: str) -> Optional[dict]:
    """A produced item -> what Liquidsoap needs: a path and metadata."""
    if item.get("status") == "live" and item.get("segment") == "time_check":
        out = _time_check_now(item)
    elif item.get("status") == "ready" and item.get("path") and os.path.exists(item["path"]):
        out = {"kind": item["kind"], "path": item["path"], "title": item.get("title") or item.get("name") or "",
               "host": item.get("host"), "bank_id": item.get("bank_id"), "seconds": item.get("seconds")}
        if item.get("story"):
            out["ref"] = f"story:{item['story']}"
            out["item_id"] = item["story"]
    else:
        return None
    if out:
        out.update(sheet_id=sheet_id, n=str(item["n"]), segment=item["segment"])
    return out


def next_item() -> dict:
    """What Liquidsoap should play next. Always answers something."""
    from ..db import repo

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
        return _idle("no block ready")

    total = len(sheet["items"])
    for _ in range(total + 1):
        idx = sheet["cursor"]
        if idx >= total:
            break
        item = sheet["items"][idx]
        repo.radio_advance_sheet(sheet["sheet_id"])
        sheet["cursor"] = idx + 1
        # Running low matters only when nothing is planned behind this block.
        if total - sheet["cursor"] <= REPLAN_AT and len(repo.radio_open_sheets()) <= 1:
            request_plan()
        served = _serve(item, sheet["sheet_id"])
        if served:
            log("director", f"served item {idx + 1}/{total}: {item['segment']} — {str(served.get('title'))[:60]}",
                kind=served["kind"], index=idx, of=total, sheet_id=sheet["sheet_id"],
                host=served.get("host"), bank_id=served.get("bank_id"), segment=item["segment"])
            return served
    return _idle("block finished")


def _recently_played(hours: int = STOCK_WINDOW_HOURS) -> List[str]:
    """Stock ids played or handed out in the window, newest first.

    Two sources, because the DJ fetches ahead: its reports arrive a track
    or two after an item was served, so what the director itself handed
    out in the window counts as played.
    """
    from ..db import repo

    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    stamped = []
    for r in repo.radio_recent_events(hours=hours):
        bid = (r.get("meta") or {}).get("bank_id")
        if bid:
            stamped.append((r.get("at") or "", bid))
    for r in repo.radio_log_tail(limit=400):
        bid = (r.get("meta") or {}).get("bank_id")
        if r.get("component") == "director" and bid and (r.get("at") or "") >= cutoff:
            stamped.append((r["at"], bid))
    seen, out = set(), []
    for _at, bid in sorted(stamped, reverse=True):
        if bid not in seen:
            seen.add(bid)
            out.append(bid)
    return out


def _rerun(recent_ids: List[str]) -> Optional[dict]:
    """An evergreen piece from an earlier block that has not played lately."""
    from ..db import repo

    for sh in repo.radio_list_sheets(limit=40):
        for it in sh["items"]:
            rid = f"{sh['sheet_id']}-{it.get('n')}"
            if (it.get("segment") in EVERGREEN and it.get("status") == "ready" and it.get("path")
                    and os.path.exists(it["path"]) and rid not in recent_ids):
                return {"kind": it["kind"], "path": it["path"], "title": it.get("title") or it.get("name") or "",
                        "host": it.get("host"), "bank_id": rid, "seconds": it.get("seconds"),
                        "segment": it["segment"], "rerun": True}
    return None


def _idle(why: str) -> dict:
    """The station with nothing new to say: two beds, an ident, something
    evergreen from the shelf, and round again. Asks for a block, which is
    granted only if someone is listening."""
    from ..db import repo

    request_plan(reason=why)
    show_key = show_at(station_now()).key
    n = int(repo.get_setting(SETTING_IDLE_N, 0) or 0)
    repo.set_setting(SETTING_IDLE_N, (n + 1) % 4)
    recent = _recently_played(hours=6 if n % 4 == 3 else STOCK_WINDOW_HOURS)
    picked = None
    if n % 4 == 3:
        picked = _rerun(recent)
    elif n % 4 == 2:
        b = pick_from_bank("jingle", avoid_ids=recent, show=show_key) \
            or pick_from_bank("station_id", avoid_ids=recent, show=show_key)
        if b:
            picked = {"kind": "station_id", "path": b["path"], "title": b.get("text") or "H.N.F.M.",
                      "host": b.get("host"), "bank_id": b["id"], "segment": "ident"}
    if not picked:
        b = pick_from_bank("track", avoid_ids=recent, show=show_key) \
            or pick_from_bank("music", avoid_ids=recent, show=show_key)
        if not b:
            return _safety()
        picked = {"kind": "music", "path": b["path"], "title": b.get("style") or "music",
                  "bank_id": b["id"], "seconds": b.get("seconds"), "segment": "music"}
    picked["hold"] = True
    log("director", f"on the library ({why}): {picked.get('segment')} — {str(picked.get('title'))[:50]}",
        kind=picked["kind"], hold=True, bank_id=picked.get("bank_id"))
    return picked


def _time_check_now(item: dict) -> Optional[dict]:
    """The time as it is when the line airs, in the station's own zone.
    One short synthesis, cached per minute. None if the voice is away."""
    from .copy import time_words
    from .library import bank_dir
    from .voice import say

    now = station_now()
    host = item.get("host") or "sofia"
    line = f"It's {time_words(now)}, on H.N.F.M."
    out = os.path.join(bank_dir(), f"time_{now.strftime('%H%M')}_{host}.mp3")
    if not os.path.exists(out) and not say(line, host, out):
        return None
    return {"kind": "time_check", "path": out, "title": line, "host": host,
            "bank_id": f"time-{now.strftime('%H%M')}"}


def _safety() -> dict:
    """The shelf is empty: the safety bed if there is one, else quiet. On a
    first start there is neither bed nor safety file, and handing the DJ a
    path that does not exist made it ask again every three seconds."""
    path = safety_path()
    if not os.path.exists(path):
        from . import mix

        quiet = os.path.join(radio_root(), "quiet.mp3")
        if os.path.exists(quiet) or mix.silence(quiet):
            path = quiet
    return {"kind": "music", "path": path, "title": "HNFM", "safety": True}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def record_event(meta: dict) -> dict:
    """Liquidsoap's report of what just started."""
    from ..db import repo

    kind = meta.get("hnfm_kind")
    if not kind:
        # Not one of ours: the safety bed, a blank. The history is what the
        # station chose to play.
        return {"ignored": True, "reason": "no hnfm_kind"}
    title = meta.get("title") or meta.get("filename") or ""
    ref = meta.get("hnfm_ref") or None
    keep = {k: v for k, v in meta.items() if k in (
        "hnfm_kind", "hnfm_ref", "hnfm_host", "hnfm_bank_id", "hnfm_sheet", "hnfm_n", "hnfm_segment",
        "filename", "title") and v not in (None, "")}
    if keep.get("hnfm_bank_id"):
        keep["bank_id"] = keep.pop("hnfm_bank_id")
    # The same file can be announced twice within a moment (the request,
    # then the decoder); one play is one row.
    last = repo.radio_recent_events(hours=1, limit=1)
    if last:
        prev = last[-1]
        same = (prev.get("ref") or "") == (ref or "") and prev.get("title") == title \
            and (prev.get("meta") or {}).get("bank_id") == keep.get("bank_id")
        try:
            age = (datetime.utcnow() - datetime.fromisoformat(prev["at"])).total_seconds()
        except Exception:
            age = 999
        if same and age < 8:
            return {"ignored": True, "reason": "duplicate announcement"}
    log("dj", f"on air: {meta.get('hnfm_segment') or kind} — {title[:60]}", kind=kind, ref=ref,
        host=meta.get("hnfm_host") or None)
    return repo.radio_record_event(kind=kind, title=title, ref=ref, meta=keep)


def now_playing() -> Optional[dict]:
    """What is on air, with everything the station knows about it: the
    show, the segment, who is speaking and the words."""
    from ..db import repo

    ev = repo.radio_recent_events(hours=6, limit=1)
    if not ev:
        return None
    e = dict(ev[-1])
    meta = e.get("meta") or {}
    if e.get("ref"):
        parsed = parse_ref(e["ref"])
        if parsed:
            e["item_id"], e["run"], e["seg"] = parsed
        elif str(e["ref"]).startswith("story:"):
            e["item_id"] = int(str(e["ref"])[6:])
    e["segment"] = meta.get("hnfm_segment")
    e["host"] = meta.get("hnfm_host")
    sheet_id, n = meta.get("hnfm_sheet"), meta.get("hnfm_n")
    if sheet_id and n not in (None, ""):
        sheet = repo.radio_get_sheet(sheet_id)
        try:
            item = sheet["items"][int(n)] if sheet else None
        except (IndexError, ValueError):
            item = None
        if item:
            e.update(segment=item.get("segment"), name=item.get("name"), text=item.get("text"),
                     lyrics=item.get("lyrics"), speakers=item.get("speakers"), seconds=item.get("seconds"),
                     block=sheet.get("title"))
    return e


def on_air() -> dict:
    """The show that is on, for the listen page."""
    sh = show_at(station_now())
    return {"key": sh.key, "name": sh.name, "tagline": sh.tagline, "anchor": sh.anchor,
            "cohost": sh.cohost, "start": sh.start, "end": sh.end}


def status() -> dict:
    """Everything the page and the monitor want in one call."""
    from .library import bank_counts

    sheet = current_sheet()
    return {
        "enabled": True,
        "now": now_playing(),
        "show": on_air(),
        "schedule": schedule(),
        "queue": queue(),
        "sheet": None if not sheet else {
            "sheet_id": sheet["sheet_id"], "title": sheet["title"],
            "source": sheet["source"], "cursor": sheet["cursor"],
            "items": len(sheet["items"]), "created_at": sheet["created_at"],
        },
        "bank": bank_counts(),
        "episodes": len(episodes(limit=200)),
        "icecast": icecast_status(),
        "audience": audience(),
        "produce": {"mode": produce_mode(), "producing": should_produce()},
        "root": radio_root(),
    }


def icecast_status(timeout: int = 5) -> dict:
    """Listeners and mounts from Icecast's status JSON, or why not."""
    import requests

    base = os.getenv("ICECAST_BASE_URL", "http://icecast:8000").rstrip("/")
    try:
        r = requests.get(f"{base}/status-json.xsl", timeout=timeout)
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
