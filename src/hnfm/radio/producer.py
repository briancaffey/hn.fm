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
from .copy import time_words
from .schemas import HOSTS, RunItem, RunSheet

logger = logging.getLogger(__name__)

TASK = "radio.plan"
MAX_LINE_WORDS = 25
# A block with fewer stories than this is not a block; use the fallback.
# One fresh story is a block. The station would rather say one new thing
# than fill the gap with station IDs, which is what a rejected block became.
MIN_STORIES = 1
# How many episodes and stories the model is shown. More is tokens, not quality.
SHOW_EPISODES = 8
SHOW_STORIES = 18
# Deep dives per block. The station is briefs; an episode is the exception.
MAX_EPISODES = int(os.getenv("RADIO_MAX_EPISODES", "0"))
# Features (sixty to ninety seconds on a story) and bits per block.
MAX_FEATURES = int(os.getenv("RADIO_MAX_FEATURES", "1"))
MAX_BITS = int(os.getenv("RADIO_MAX_BITS", "2"))
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
    from .bits import listing as bits_listing
    from .voice import host_listing

    now = now or datetime.now()
    used_eps, used_stories = used_refs(recent, planned)
    # Aired is aired: no falling back to the whole library when every
    # episode has played this week.
    fresh_eps = [e for e in eps if e["ref"] not in used_eps]
    fresh_stories = [st for st in stories if st["item_id"] not in used_stories]

    svc = LLMService(task=TASK)
    log("producer", f"thinking: asking {svc.model} for a {minutes}-minute block from "
        f"{min(len(fresh_stories), SHOW_STORIES)} new stories and {min(len(fresh_eps), SHOW_EPISODES)} episodes",
        model=svc.model, minutes=minutes)
    try:
        prompt = render(
            TASK, now=f"{now.strftime('%A')}, {time_words(now)}", minutes=minutes,
            hosts=host_listing(), stories=_stories_listing(fresh_stories[:SHOW_STORIES]),
            bits=bits_listing(),
            episodes=_episode_listing(fresh_eps[:SHOW_EPISODES]),
            recent=_recent_listing(recent[-14:]), planned=_planned_listing(planned[:20]),
        )
        raw = svc.generate_structured(prompt, RunSheet)
        sheet = enforce(raw, {e["ref"]: e for e in eps}, {st["item_id"] for st in stories},
                        used_eps, used_stories, minutes)
        sheet = complete(sheet, fresh_stories, minutes, now)
        n_stories = sum(1 for i in sheet.items if i.kind in ("episode", "brief", "feature"))
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
    n_eps = n_features = n_bits = 0
    used_bits = set()
    used_styles = set()
    by_item = {}
    for ref, e in by_ref.items():
        by_item.setdefault(str(e.get("item_id")), ref)

    for it in sheet.items:
        # The model sometimes files a bit under kind=brief with the bit key
        # set and no story. It meant a bit.
        if it.kind == "brief" and it.bit and not it.story:
            it.kind = "bit"
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
        elif it.kind in ("brief", "feature"):
            if it.story is None or it.story not in story_ids:
                continue
            if it.story in used_st:
                # The model briefs a story and then features it. The feature
                # is the fuller treatment: keep it, drop the earlier brief.
                if it.kind == "feature" and n_features < MAX_FEATURES:
                    out = [o for o in out if not (o.kind == "brief" and o.story == it.story)]
                else:
                    continue
            if it.kind == "feature" and n_features >= MAX_FEATURES:
                it.kind = "brief"
            if it.host not in HOSTS or it.host == "dia" or it.host == _last_speaker(out):
                it.host = _next_host(out)
            it.mood = it.mood if it.mood in ("calm", "neutral", "sad") else "calm"
            it.line = None
            used_st.add(it.story)
            if it.kind == "feature":
                n_features += 1
                total += 75
            else:
                total += 30
        elif it.kind == "bit":
            from .bits import BITS

            if it.bit not in BITS or it.bit in used_bits or n_bits >= MAX_BITS:
                continue
            if out and out[-1].kind == "bit":
                continue
            it.host = BITS[it.bit]["host"]
            it.mood = BITS[it.bit]["mood"]
            it.line = None
            used_bits.add(it.bit)
            n_bits += 1
            total += 45
        elif it.kind == "music":
            from .music import STYLES

            it.seconds = max(MUSIC_MIN, min(int(it.seconds or 30), MUSIC_MAX))
            style = (it.music_style or "").strip()[:120]
            # The model likes one style for the whole block; the station does not.
            if not style or style in used_styles:
                style = next((st for st in STYLES if st not in used_styles), STYLES[len(used_styles) % len(STYLES)])
            it.music_style = style
            used_styles.add(style)
            total += it.seconds
        else:
            if it.host not in HOSTS or (it.kind != "station_id" and it.host == _last_speaker(out)):
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


def complete(sheet: RunSheet, fresh_stories: List[dict], minutes: int,
             now: Optional[datetime] = None) -> RunSheet:
    """Give the block its shape whatever the model left out.

    The model is asked for six to nine briefs, one feature, one or two
    bits and short beds between; it does not always deliver. Rather than
    throw a block away for a missing feature, fill it in: briefs from the
    fresh pool, a feature in the middle, a bit or two, a bed after every
    second spoken item. The model's choices stay where they were.
    """
    from .bits import BITS
    from .music import STYLES

    now = now or datetime.now()
    items = list(sheet.items)
    used_stories = {i.story for i in items if i.story}
    pool = [st for st in fresh_stories if st["item_id"] not in used_stories]
    hosts = [h for h in HOSTS if h != "dia"]

    def host_after(seq: List[RunItem]) -> str:
        last = next((i.host for i in reversed(seq) if i.host), None)
        return hosts[(hosts.index(last) + 1) % len(hosts)] if last in hosts else hosts[0]

    # Enough briefs.
    n_briefs = sum(1 for i in items if i.kind == "brief")
    while n_briefs < 6 and pool:
        st = pool.pop(0)
        items.append(RunItem(kind="brief", story=st["item_id"], host=host_after(items), mood="calm"))
        n_briefs += 1

    # A feature in the middle, announced.
    if MAX_FEATURES and not any(i.kind == "feature" for i in items) and pool:
        st = pool.pop(0)
        mid = max(2, len(items) // 2)
        items[mid:mid] = [
            RunItem(kind="coming_up", host=host_after(items[:mid]), mood="calm",
                    line=f"Coming up, the story: {st['title'][:80]}."),
            RunItem(kind="feature", story=st["item_id"], host="jason", mood="calm"),
        ]

    # A bit or two, spaced.
    have_bits = [i.bit for i in items if i.kind == "bit"]
    keys = [k for k in BITS if k != "feature" and k not in have_bits]
    want = min(MAX_BITS, 2) - len(have_bits)
    for n in range(max(0, want)):
        if not keys:
            break
        key = keys.pop((now.hour + n) % len(keys))
        at = 3 if n == 0 else min(len(items), 9)
        while at < len(items) and items[at].kind in ("bit", "coming_up", "feature"):
            at += 1
        items.insert(min(at, len(items)), RunItem(kind="bit", bit=key, host=BITS[key]["host"], mood=BITS[key]["mood"]))

    # A bed after every second spoken item that is not already followed by one.
    out: List[RunItem] = []
    spoken_run = 0
    used_styles = {i.music_style for i in items if i.kind == "music" and i.music_style}
    for i in items:
        out.append(i)
        if i.kind == "music":
            spoken_run = 0
            continue
        spoken_run += 1
        if spoken_run >= 2 and i.kind in ("brief", "feature", "bit"):
            style = next((st for st in STYLES if st not in used_styles), STYLES[len(used_styles) % len(STYLES)])
            used_styles.add(style)
            out.append(RunItem(kind="music", music_style=style, seconds=30))
            spoken_run = 0
    return RunSheet(title=sheet.title, items=out)


def _last_speaker(items: List[RunItem]) -> Optional[str]:
    return next((i.host for i in reversed(items) if i.host and i.kind != "music"), None)


def _next_host(items: List[RunItem]) -> str:
    last = next((i.host for i in reversed(items) if i.host), None)
    order = [h for h in HOSTS if h != "dia"]
    if last in order:
        return order[(order.index(last) + 1) % len(order)]
    return order[0]


def hold_block(now: Optional[datetime] = None) -> RunSheet:
    """Nothing fresh to say: two beds, no talking. A station ID between two
    silences is the loop the listener heard — "You're listening to HNFM"
    eleven times in a minute — so a hold is music until there is news."""
    from .music import STYLES

    now = now or datetime.now()
    return RunSheet(title=f"HNFM · {now.strftime('%-I %p')} hold", items=[
        RunItem(kind="music", music_style=STYLES[now.minute % len(STYLES)], seconds=40),
        RunItem(kind="music", music_style=STYLES[(now.minute + 3) % len(STYLES)], seconds=40),
    ])


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
    st_pool = [st for st in stories if st["item_id"] not in used_stories]
    if not st_pool:
        return hold_block(now)
    hosts = ["mia", "jason", "sofia", "leo", "aria", "ray"]
    items: List[RunItem] = [RunItem(kind="station_id", host="mia", mood="calm")]
    items.append(RunItem(kind="time_check", host="sofia", mood="calm",
                         line=f"It's {time_words(now)}, on HNFM."))
    from .bits import BITS

    total, i = 12.0, 0
    target = minutes * 60
    feature_at = max(3, min(len(st_pool) // 2, 5))
    bit_keys = [k for k in BITS if k != "feature"]
    bit_at = {2: bit_keys[now.hour % len(bit_keys)], 7: bit_keys[(now.hour + 1) % len(bit_keys)]}
    while total < target and st_pool:
        if i in bit_at:
            key = bit_at[i]
            items.append(RunItem(kind="bit", bit=key, host=BITS[key]["host"], mood=BITS[key]["mood"]))
            total += 45
        if i == feature_at and MAX_FEATURES:
            st = st_pool.pop(0)
            items.append(RunItem(kind="coming_up", host=hosts[i % 6], mood="calm",
                                 line=f"Coming up, the story: {st['title'][:80]}."))
            items.append(RunItem(kind="feature", story=st["item_id"], host="jason", mood="calm"))
            total += 83
        else:
            st = st_pool.pop(0)
            items.append(RunItem(kind="brief", story=st["item_id"], host=hosts[i % 6], mood="calm"))
            total += 30
        if i % 2 == 1:
            items.append(RunItem(kind="music", music_style=STYLES[i % len(STYLES)], seconds=30))
            total += 30
        if i % 4 == 3:
            items.append(RunItem(kind="station_id", host=hosts[(i + 1) % 6], mood="calm"))
            total += 6
        i += 1
    return RunSheet(title=f"HNFM · {now.strftime('%-I %p')} block", items=items)
