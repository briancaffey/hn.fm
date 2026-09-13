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
from datetime import datetime
from typing import Dict, List, Optional

from .schemas import HOSTS, RunItem, RunSheet

logger = logging.getLogger(__name__)

TASK = "radio.plan"
MAX_LINE_WORDS = 25
# A block with fewer episodes than this is not a block; use the fallback.
MIN_EPISODES = 2
# How many episodes the model is shown. More is tokens, not quality.
SHOW_EPISODES = 16

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


def plan_block(eps: List[dict], recent: List[dict], minutes: int = 30,
               now: Optional[datetime] = None) -> tuple:
    """(RunSheet, source, usage) — source is "llm" or "fallback"."""
    from ..content.llm_service import LLMService
    from ..content.prompts import render
    from .voice import host_listing

    now = now or datetime.now()
    recent_refs = {r.get("ref") for r in recent if r.get("ref")}
    fresh = [e for e in eps if e["ref"] not in recent_refs]
    if not fresh:
        fresh = eps  # everything has aired: the model may repeat the oldest

    svc = LLMService(task=TASK)
    try:
        prompt = render(
            TASK, now=now.strftime("%A %-I:%M %p"), minutes=minutes,
            hosts=host_listing(), episodes=_episode_listing(fresh[:SHOW_EPISODES]),
            recent=_recent_listing(recent[-12:]),
        )
        raw = svc.generate_structured(prompt, RunSheet)
        sheet = enforce(raw, {e["ref"]: e for e in eps}, recent_refs, minutes)
        n_eps = sum(1 for i in sheet.items if i.kind == "episode")
        logger.info(
            f"radio producer: model wrote {len(raw.items)} items, {len(sheet.items)} kept, "
            f"{n_eps} episodes ({svc.usage['tokens_in']}/{svc.usage['tokens_out']} tokens)"
        )
        if n_eps >= MIN_EPISODES:
            return sheet, "llm", dict(svc.usage)
        logger.warning(
            f"radio producer: only {n_eps} episode(s) in the plan (a cut-off or thin "
            f"answer); falling back"
        )
    except Exception as e:
        logger.warning(f"radio producer: model failed ({e}); falling back")
    return fallback_block(eps, recent, minutes, now), "fallback", dict(svc.usage)


def enforce(sheet: RunSheet, by_ref: Dict[str, dict], recent_refs: set,
            minutes: int) -> RunSheet:
    """The station's rules, applied to whatever the model returned."""
    out: List[RunItem] = []
    used = set()
    budget = minutes * 60 + 180
    total = 0.0
    # The model writes the ref it was shown — usually. It has also written the
    # bare story id, and once "id:run". Resolve those to the listed episode
    # for that story rather than throwing the whole block away.
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
            if not e or ref in used or ref in recent_refs:
                continue
            if out and out[-1].kind == "episode":
                out.append(RunItem(kind="station_id", host=_next_host(out), line=None))
            used.add(ref)
            total += e.get("seconds") or 120
        elif it.kind == "music":
            it.seconds = max(45, min(int(it.seconds or 60), 90))
            it.music_style = (it.music_style or "warm lo-fi piano, 72 bpm, instrumental")[:120]
            total += it.seconds
        else:
            if it.host not in HOSTS:
                it.host = _next_host(out)
            if it.line:
                words = it.line.split()
                it.line = " ".join(words[:MAX_LINE_WORDS])
            if it.kind == "coming_up" and not it.line:
                continue
            total += 8
        if total > budget:
            break
        out.append(it)
    if out and out[0].kind != "station_id":
        out.insert(0, RunItem(kind="station_id", host=_next_host([]), line=None))
    return RunSheet(title=sheet.title or "HNFM", items=out)


def _next_host(items: List[RunItem]) -> str:
    last = next((i.host for i in reversed(items) if i.host), None)
    order = [h for h in HOSTS if h != "dia"]
    if last in order:
        return order[(order.index(last) + 1) % len(order)]
    return order[0]


def fallback_block(eps: List[dict], recent: List[dict], minutes: int = 30,
                   now: Optional[datetime] = None) -> RunSheet:
    """A block with no model: ID, episode, bed, ID, episode, coming-up…

    Newest episodes that have not aired recently, a music bed between
    them, a station ID every third item, a time check at the top of the
    block. Deterministic, so the same inputs plan the same block.
    """
    from .music import STYLES

    now = now or datetime.now()
    recent_refs = {r.get("ref") for r in recent if r.get("ref")}
    pool = [e for e in eps if e["ref"] not in recent_refs] or list(eps)
    items: List[RunItem] = [RunItem(kind="station_id", host="mia")]
    items.append(RunItem(kind="time_check", host="sofia",
                         line=f"It's {now.strftime('%-I:%M')} on HNFM."))
    total, i = 0.0, 0
    hosts = ["mia", "jason", "sofia", "leo"]
    while pool and total < minutes * 60:
        e = pool.pop(0)
        if items[-1].kind == "episode":
            items.append(RunItem(kind="coming_up", host=hosts[i % 4],
                                 line=f"Coming up: {e['title'][:80]}."))
        items.append(RunItem(kind="episode", episode=e["ref"]))
        total += e.get("seconds") or 120
        items.append(RunItem(kind="music", music_style=STYLES[i % len(STYLES)], seconds=60))
        total += 60
        if i % 2 == 1:
            items.append(RunItem(kind="station_id", host=hosts[(i + 1) % 4]))
        i += 1
    return RunSheet(title=f"HNFM · {now.strftime('%-I %p')} block", items=items)
