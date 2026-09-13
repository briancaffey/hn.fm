"""The producer: plans the next block of programming (plans/20).

One structured call to the local model per block — about thirty minutes of
air for a couple of thousand tokens — with a deterministic fallback that
produces a perfectly listenable block when the model is down. Both return
a `RunSheet`; the director does not care which wrote it.

Guardrails after the model, not instead of it: episodes it names must
exist and not have just aired, hosts must be real, lines are capped, and
two episodes are never adjacent. The model chooses; the code enforces.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from . import log
from .schemas import HOSTS, RunItem, RunSheet

logger = logging.getLogger(__name__)

TASK = "radio.plan"
MAX_LINE_WORDS = 25
# A block with fewer stories than this is not a block; use the fallback.
MIN_STORIES = 3
# How many episodes and stories the model is shown. More is tokens, not quality.
SHOW_EPISODES = 8
SHOW_STORIES = 18
# Deep dives per block. The station is briefs; an episode is the exception.
MAX_EPISODES = int(os.getenv("RADIO_MAX_EPISODES", "1"))
MUSIC_MIN, MUSIC_MAX = 20, 45

STATION_IDS = [
    "You're listening to HNFM.",
    "This is HNFM. Hacker News, on air.",
    "HNFM. Stories from the front page, read aloud.",
    "You're on HNFM, where the comments get a voice.",
    "HNFM. Made by machines, about what people are building.",
    "Stay with us. This is HNFM.",
]


def _episode_listing(eps: List[dict]) -> str:
    return "\n".join(
        f"- {e['ref']} · {round((e.get('seconds') or 0) / 60, 1)} min · "
        f"{e.get('age_hours') if e.get('age_hours') is not None else '?'} h old · {e['title'][:90]}"
        for e in eps
    ) or "(none)"


def _recent_listing(recent: List[dict]) -> str:
    return "\n".join(
        f"- {r.get('kind')}: {r.get('title') or ''}" + (f" [{r['ref']}]" if r.get("ref") else "")
        for r in recent
    ) or "(nothing yet)"


def _stories_listing(stories: List[dict]) -> str:
    return "\n".join(
        f"- {st['item_id']} · {st.get('age_hours') if st.get('age_hours') is not None else '?'} h · {st['title'][:90]}"
        for st in stories
    ) or "(none)"


def _planned_listing(planned: List[dict]) -> str:
    return "\n".join(
        f"- {it.get('kind')}: {it.get('episode') or it.get('story') or it.get('line') or ''}"
        for it in planned
    ) or "(nothing)"


def used_refs(recent: List[dict], planned: List[dict]) -> tuple:
    """(episode refs, story ids) that must not be scheduled again."""
    eps = {r.get("ref") for r in recent if r.get("ref") and ":" in str(r.get("ref")) and not str(r["ref"]).startswith("story:")}
    stories = {int(str(r["ref"])[6:]) for r in recent if str(r.get("ref") or "").startswith("story:")}
    for it in planned:
        if it.get("episode"):
            eps.add(it["episode"])
        if it.get("story"):
            stories.add(int(it["story"]))
    return eps, stories


def plan_block(eps: List[dict], stories: List[dict], recent: List[dict], planned: List[dict],
               minutes: int = 30, now: Optional[datetime] = None) -> tuple:
    """(RunSheet, source, usage) — source is "llm" or "fallback"."""
    from ..content.llm_service import LLMService
    from ..content.prompts import render
    from .voice import host_listing

    now = now or datetime.now()
    used_eps, used_stories = used_refs(recent, planned)
    fresh_eps = [e for e in eps if e["ref"] not in used_eps] or list(eps)
    fresh_stories = [st for st in stories if st["item_id"] not in used_stories]

    svc = LLMService(task=TASK)
    log("producer", f"thinking: asking {svc.model} for a {minutes}-minute block from "
        f"{min(len(fresh_stories), SHOW_STORIES)} new stories and {min(len(fresh_eps), SHOW_EPISODES)} episodes",
        model=svc.model, minutes=minutes)
    try:
        prompt = render(
            TASK, now=now.strftime("%A %-I:%M %p"), minutes=minutes,
            hosts=host_listing(), stories=_stories_listing(fresh_stories[:SHOW_STORIES]),
            episodes=_episode_listing(fresh_eps[:SHOW_EPISODES]),
            recent=_recent_listing(recent[-14:]), planned=_planned_listing(planned[:20]),
        )
        raw = svc.generate_structured(prompt, RunSheet)
        sheet = enforce(raw, {e["ref"]: e for e in eps}, {st["item_id"] for st in stories},
                        used_eps, used_stories, minutes)
        n_stories = sum(1 for i in sheet.items if i.kind in ("episode", "brief"))
        logger.info(
            f"radio producer: model wrote {len(raw.items)} items, {len(sheet.items)} kept, "
            f"{n_stories} stories ({svc.usage['tokens_in']}/{svc.usage['tokens_out']} tokens)"
        )
        if n_stories >= MIN_STORIES:
            return sheet, "llm", dict(svc.usage)
        logger.warning(f"radio producer: only {n_stories} stories in the plan; falling back")
        log("producer", f"the model's block had only {n_stories} stories; using the deterministic producer")
    except Exception as e:
        logger.warning(f"radio producer: model failed ({e}); falling back")
        log("producer", f"the model did not answer ({str(e)[:60]}); using the deterministic producer")
    return fallback_block(eps, stories, recent, planned, minutes, now), "fallback", dict(svc.usage)


def enforce(sheet: RunSheet, by_ref: Dict[str, dict], story_ids: set, used_eps: set,
            used_stories: set, minutes: int) -> RunSheet:
    """The station's rules, applied to whatever the model returned."""
    out: List[RunItem] = []
    used = set(used_eps)
    used_st = set(used_stories)
    budget = minutes * 60 + 180
    total = 0.0
    n_eps = 0
    by_item = {}
    for ref, e in by_ref.items():
        by_item.setdefault(str(e.get("item_id")), ref)

    for it in sheet.items:
        if it.kind == "episode":
            ref = (it.episode or "").strip()
            if ref not in by_ref:
                ref = by_item.get(ref.split(":")[0], ref)
            it.episode = ref
            e = by_ref.get(ref)
            if not e or ref in used or n_eps >= MAX_EPISODES:
                continue
            if out and out[-1].kind in ("episode", "brief"):
                out.append(RunItem(kind="station_id", host=_next_host(out), mood="calm"))
            used.add(ref)
            n_eps += 1
            total += e.get("seconds") or 120
        elif it.kind == "brief":
            if it.story is None or it.story not in story_ids or it.story in used_st:
                continue
            if it.host not in HOSTS or it.host == "dia":
                it.host = _next_host(out)
            it.mood = it.mood if it.mood in ("calm", "neutral", "sad") else "calm"
            it.line = None
            used_st.add(it.story)
            total += 30
        elif it.kind == "music":
            it.seconds = max(MUSIC_MIN, min(int(it.seconds or 30), MUSIC_MAX))
            it.music_style = (it.music_style or "warm lo-fi piano, 72 bpm, instrumental")[:120]
            total += it.seconds
        else:
            if it.host not in HOSTS:
                it.host = _next_host(out)
            it.mood = it.mood if it.mood in ("calm", "neutral", "sad") else "calm"
            if it.line:
                it.line = " ".join(it.line.split()[:MAX_LINE_WORDS])
            if it.kind == "coming_up" and not it.line:
                continue
            total += 8
        if total > budget:
            break
        out.append(it)
    if out and out[0].kind != "station_id":
        out.insert(0, RunItem(kind="station_id", host=_next_host([]), mood="calm"))
    return RunSheet(title=sheet.title or "HNFM", items=out)


def _next_host(items: List[RunItem]) -> str:
    last = next((i.host for i in reversed(items) if i.host), None)
    order = [h for h in HOSTS if h != "dia"]
    if last in order:
        return order[(order.index(last) + 1) % len(order)]
    return order[0]


def fallback_block(eps: List[dict], stories: List[dict], recent: List[dict], planned: List[dict],
                   minutes: int = 30, now: Optional[datetime] = None) -> RunSheet:
    """A block with no model: ID, time check, then briefs with short beds
    between, one episode in the middle, an ID every few items.

    Deterministic, so the same inputs plan the same block; and it never
    repeats what aired or is already on the belt.
    """
    from .music import STYLES

    now = now or datetime.now()
    used_eps, used_stories = used_refs(recent, planned)
    ep_pool = [e for e in eps if e["ref"] not in used_eps]
    st_pool = [st for st in stories if st["item_id"] not in used_stories]
    hosts = ["mia", "jason", "sofia", "leo", "aria", "ray"]
    items: List[RunItem] = [RunItem(kind="station_id", host="mia", mood="calm")]
    items.append(RunItem(kind="time_check", host="sofia", mood="calm",
                         line=f"It's {now.strftime('%-I:%M')} on HNFM."))
    total, i = 12.0, 0
    target = minutes * 60
    deep_at = max(3, len(st_pool) // 2)
    while total < target and (st_pool or (ep_pool and i == deep_at)):
        if i == deep_at and ep_pool:
            e = ep_pool.pop(0)
            items.append(RunItem(kind="coming_up", host=hosts[i % 6], mood="calm",
                                 line=f"Coming up, a deep dive: {e['title'][:80]}."))
            items.append(RunItem(kind="episode", episode=e["ref"]))
            total += (e.get("seconds") or 120) + 8
        elif st_pool:
            st = st_pool.pop(0)
            items.append(RunItem(kind="brief", story=st["item_id"], host=hosts[i % 6], mood="calm"))
            total += 30
        else:
            break
        if i % 2 == 1:
            items.append(RunItem(kind="music", music_style=STYLES[i % len(STYLES)], seconds=30))
            total += 30
        if i % 4 == 3:
            items.append(RunItem(kind="station_id", host=hosts[(i + 1) % 6], mood="calm"))
            total += 6
        i += 1
    return RunSheet(title=f"HNFM · {now.strftime('%-I %p')} block", items=items)
