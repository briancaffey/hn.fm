"""The planner: the next block, as a list of concrete items (issue #28).

The shape comes from the format clock and cannot be changed by a model.
The one editorial decision — which story goes in which slot, and from what
angle — is asked of the model once per block (`radio.assign`), checked
against the slot's own rules, and completed in order of freshness where the
model left a gap or was away. There is nothing to repair afterwards,
because nothing the model returns can alter the running order.

    candidates()         stories the station could talk about, with fact sheets
    plan(now, quarter)   -> {title, show, quarter, items, source, usage}
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from . import log
from .format import Show, Slot, rundown, show_at, station_now
from .segments import SEGMENTS, resolve_bit, segment, story_matches

logger = logging.getLogger(__name__)

# How many candidates get a fact sheet (one small model call each, once
# per story ever) and are shown to the producer.
SHOW_STORIES = int(os.getenv("RADIO_SHOW_STORIES", "16"))


def recent_stories(limit: int = 60, hours: int = 48) -> List[dict]:
    """Stories posted lately that triage did not rule out, freshest first.
    From /new and from the front page: a front-page story is the one with
    a discussion, and the comment line needs a discussion."""
    from ..db import repo

    rows, _ = repo.list_triage(offset=0, limit=400, include_generated=True, since_hours=hours)
    out = []
    for r in rows:
        if (r.get("verdict") or "") == "unsuitable" or not r.get("title"):
            continue
        age = None
        if r.get("time"):
            age = round((datetime.utcnow() - datetime.utcfromtimestamp(int(r["time"]))).total_seconds() / 3600, 1)
            if age > hours:
                continue
        out.append({"item_id": r["item_id"], "title": r["title"], "age_hours": age})
    out.sort(key=lambda x: x["age_hours"] if x["age_hours"] is not None else 1e9)
    return out[:limit]


def candidates(limit: int = SHOW_STORIES, hours: int = 48, exclude: Optional[set] = None) -> List[dict]:
    """Recent stories with a fact sheet, freshest first.

    [{item_id, title, age_hours, score, comments, kind, discussed, what}]

    A story needs a sheet to be a candidate, and a sheet is one small
    model call the first time, so only as many are made as will be shown.
    """
    from .sheets import sheet_for

    exclude = exclude or set()
    out = []
    for st in recent_stories(limit=limit * 3, hours=hours):
        if st["item_id"] in exclude:
            continue
        s = sheet_for(st["item_id"])
        if not s:
            continue
        out.append({
            "item_id": st["item_id"], "title": s["title"], "age_hours": st.get("age_hours"),
            "score": s.get("score") or 0, "comments": s.get("comments") or 0, "kind": s["kind"],
            "discussed": len(s["sheet"].get("callers") or []) >= 2, "what": s["sheet"].get("what") or "",
        })
        if len(out) >= limit:
            break
    return out


def _speakers(seg, sh: Show, n: int) -> List[str]:
    """Who is in a piece. Headlines rotate through the show's whole cast,
    so the anchor is not the only voice in the half hour."""
    everyone = (sh.anchor, sh.cohost) + tuple(sh.cast)
    v = seg.voices
    if v == "anchor":
        return [sh.anchor]
    if v == "cohost":
        return [sh.cohost]
    if v == "duo":
        return [sh.anchor, sh.cohost]
    if v == "callers":
        return [sh.anchor, "caller1", "caller2", "caller3"]
    if v == "cast":
        return [everyone[n % len(everyone)]]
    return [v]  # a named host: Leo's joke is Leo's wherever it airs


def _ends_show(now: datetime, quarter: int, sh: Show) -> Optional[Show]:
    """The show that starts next hour, if this block is the last quarter of
    this show's last hour."""
    if quarter != 3:
        return None
    after = show_at(now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return after if after.key != sh.key else None


def _slots_to_items(slots: List[Slot], sh: Show, now: datetime, quarter: int) -> List[dict]:
    items, casts, bits = [], quarter, now.hour * 4 + quarter
    nxt = _ends_show(now, quarter, sh)
    for n, slot in enumerate(slots):
        key = slot.segment
        if key == "bit":
            key = resolve_bit(bits)
            bits += 1
        if nxt and n == len(slots) - 1 and key == "ident":
            key = "handoff"
        seg = segment(key)
        item = {"n": n, "segment": key, "kind": seg.kind, "show": sh.key, "name": seg.name, "quarter": quarter}
        if seg.written:
            if seg.voices == "cast":
                casts += 1
            item["speakers"] = _speakers(seg, sh, casts)
            if key == "handoff" and nxt:
                item["speakers"] = [sh.anchor, nxt.anchor]
                item["next_show"] = nxt.key
        items.append(item)
    return items


def _listing(stories: List[dict]) -> str:
    rows = []
    for s in stories:
        tags = [t for t in (s["kind"] if s["kind"] != "story" else "", "discussed" if s["discussed"] else "") if t]
        rows.append(f"- {s['item_id']} · {s['age_hours'] if s['age_hours'] is not None else '?'} h · "
                    f"{s['score']}/{s['comments']} · {', '.join(tags) or '-'} · {s['title'][:90]} — {s['what'][:110]}")
    return "\n".join(rows) or "(none)"


def _ask_producer(sh: Show, items: List[dict], stories: List[dict], used_titles: List[str], now: datetime):
    """The model's picks as {slot n: (story id, angle)}, the block's title,
    and what the call cost. Empty picks if the model is away."""
    from ..content.llm_service import LLMService
    from ..content.prompts import render
    from .copy import time_words
    from .schemas import Picks

    slots = "\n".join(
        f"- {i['n']} · {i['segment']} · {SEGMENTS[i['segment']].name}"
        + (" (discussed stories only)" if SEGMENTS[i["segment"]].stories == "discussed" else "")
        + (" (Show HN only)" if SEGMENTS[i["segment"]].stories == "show_hn" else "")
        + (" (Ask HN only)" if SEGMENTS[i["segment"]].stories == "ask_hn" else "")
        for i in items if SEGMENTS[i["segment"]].needs in ("story", "discussion"))
    svc = LLMService(task="radio.assign")
    try:
        got = svc.generate_structured(render(
            "radio.assign", show_name=sh.name, show_tone=sh.tone,
            now=f"{now.strftime('%A')}, {time_words(now)}", slots=slots, stories=_listing(stories),
            used="\n".join(f"- {t}" for t in used_titles[-12:]) or "(nothing)",
        ), Picks)
        return {p.slot: (p.story, p.angle.strip()) for p in got.picks}, got.title.strip(), dict(svc.usage)
    except Exception as e:
        logger.warning(f"radio planner: the producer did not answer ({e})")
        log("producer", f"the model did not answer ({str(e)[:60]}); filling the slots by freshness")
        return {}, "", dict(svc.usage)


def assign(items: List[dict], stories: List[dict], picks: Dict[int, tuple]) -> List[dict]:
    """Put stories in the story slots: the producer's picks where they are
    valid, then the freshest unused story that qualifies. A slot nothing
    qualifies for becomes its segment's fallback; if that has no story
    either, the slot is dropped. Pure: the same inputs give the same block.
    """
    by_id = {s["item_id"]: s for s in stories}
    used: set = set()
    out: List[dict] = []
    # First pass: honour valid picks, so a later fallback cannot steal them.
    chosen: Dict[int, tuple] = {}
    for it in items:
        seg = SEGMENTS[it["segment"]]
        if seg.needs not in ("story", "discussion"):
            continue
        pick = picks.get(it["n"])
        if pick and pick[0] in by_id and pick[0] not in used and story_matches(seg, by_id[pick[0]]):
            chosen[it["n"]] = pick
            used.add(pick[0])
    for it in items:
        seg = SEGMENTS[it["segment"]]
        if seg.needs not in ("story", "discussion"):
            out.append(it)
            continue
        it = dict(it)
        pick = chosen.get(it["n"])
        while not pick:
            st = next((s for s in stories if s["item_id"] not in used and story_matches(seg, s)), None)
            if st:
                pick = (st["item_id"], "")
                used.add(st["item_id"])
                break
            if not seg.fallback:
                break
            # Demote the slot: a Show HN desk with no Show HN is a headline.
            seg = SEGMENTS[seg.fallback]
            it.update(segment=seg.key, kind=seg.kind, name=seg.name)
            if seg.needs not in ("story", "discussion"):
                break
            if seg.voices == "cast" and len(it.get("speakers") or []) != 1:
                it["speakers"] = it["speakers"][:1]
        if seg.needs in ("story", "discussion"):
            if not pick:
                continue
            it["story"], it["angle"] = pick[0], pick[1]
            it["title"] = by_id[pick[0]]["title"]
        elif not seg.written:
            it.pop("speakers", None)
        out.append(it)
    return out


def plan(now: Optional[datetime] = None, quarter: int = 0, used_stories: Optional[set] = None,
         used_titles: Optional[List[str]] = None, stories: Optional[List[dict]] = None,
         ask_model: bool = True) -> dict:
    """The next block: quarter `quarter` of the show on air. `stories` and
    `ask_model` exist for tests and for the eval round, which plan from a
    frozen set."""
    now = now or station_now()
    sh = show_at(now)
    items = _slots_to_items(rundown(now, quarter), sh, now, quarter)
    if stories is None:
        stories = candidates(exclude=used_stories or set())
    picks, title, usage = ({}, "", {}) if not ask_model or not stories else _ask_producer(
        sh, items, stories, used_titles or [], now)
    items = assign(items, stories, picks)
    for n, it in enumerate(items):
        it["n"] = n
    n_stories = sum(1 for i in items if i.get("story"))
    log("producer", f"planned {sh.name}, quarter {quarter + 1}: {len(items)} items, {n_stories} stories"
        + (f", {len(picks)} chosen by the model" if picks else ", filled by freshness"),
        show=sh.key, quarter=quarter, items=len(items), stories=n_stories)
    return {
        "title": title or f"{sh.name} · {now.strftime('%-I:%M %p')}",
        "show": sh.key, "quarter": quarter, "items": items, "stories": n_stories,
        "source": "llm" if picks else "fallback", "usage": usage,
    }
