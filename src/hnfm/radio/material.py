"""What a segment is written from (issue #29).

One provider per kind of material a segment can need. Each returns the
text the writer sees, or None when there is nothing to write from — the
planner then uses the segment's fallback instead of airing an invention.

The writer is told to use only this. Keeping it in one module is what
makes "is this piece faithful?" a question the editor can answer.
"""

import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

TROPES = [
    "rewriting it in Rust", "the microservices that became a monolith again",
    "the meeting that could have been an email", "tabs versus spaces", "naming things", "cache invalidation",
    "the demo that only works on the presenter's laptop",
    "adding A.I. to a toaster", "the standup that runs forty minutes", "the one test that is flaky",
    "blaming D.N.S.", "the intern who pushed to main", "the framework of the month",
    "the on-call pager at three in the morning", "the ticket titled 'small fix'", "YAML indentation",
    "the startup that pivots to A.I.", "web scale", "the config file with four hundred options",
    "the dependency with one maintainer", "the benchmark nobody can reproduce", "the README that says 'coming soon'",
    "a two-line change that needs six approvals", "the dashboard nobody looks at",
]

JARGON = [
    "yak shaving", "technical debt", "the happy path", "a race condition", "idempotent",
    "eventual consistency", "a memory leak", "premature optimisation", "rubber duck debugging",
    "the bus factor", "dogfooding", "a heisenbug", "cargo cult programming", "an off-by-one error",
    "the two hard problems", "a hot path", "backpressure", "a thundering herd", "a golden path",
    "a footgun", "a flame graph", "tail latency", "a canary release", "the cold start problem",
]

# Things nobody sells, for the sponsor read.
PRODUCTS = [
    "git rebase, interactive", "the semicolon", "a second monitor", "the man page", "localhost",
    "plain text files", "the off-site backup you keep meaning to set up",
    "a mechanical keyboard with the loud switches", "the rubber duck on your desk", "U.T.C.",
    "the changelog", "a good error message", "dark mode", "the kill dash nine command",
    "regular expressions", "the staging environment", "a README with an example in it",
]


def trope(seed: int) -> str:
    return "Trope: " + TROPES[seed % len(TROPES)]


def jargon(seed: int) -> str:
    return "Term: " + JARGON[seed % len(JARGON)]


def product(seed: int) -> str:
    return "The product nobody sells: " + PRODUCTS[seed % len(PRODUCTS)]


def stack() -> str:
    """The models on the station, from what is configured, not from memory."""
    import os

    llm = os.getenv("RADIO_STACK_LLM", "Nemotron three point five Lightning")
    return "\n".join([
        f"- {llm} writes every word and plans every hour. It runs on a D.G.X. Spark in the house.",
        "- Magpie voices every host and every caller, each with a mood.",
        "- ACE-Step makes the music: every bed, every jingle, and the song of the hour.",
        "- A speech recognition model listens to each item before it airs and sends it back if a word came out wrong.",
        "- Liquidsoap is the D.J. that asks the station what to play next; Icecast sends it to listeners.",
        "- None of it leaves the house. No cloud, no keys.",
    ])


def show_material(show, coming_up: Optional[List[str]] = None, now: Optional[datetime] = None) -> str:
    from .copy import time_words
    from .format import station_now

    now = now or station_now()
    lines = [
        "Station: H.N.F.M., Hacker News on the radio.",
        f"Show: {show.name}. Its promise: {show.tagline}",
        f"The time: {time_words(now)}, {now.strftime('%A')}.",
    ]
    if coming_up:
        lines.append("Coming up this half hour (titles; say at most one, in your own words):")
        lines += [f"- {t}" for t in coming_up[:3]]
    return "\n".join(lines)


def handoff_material(outgoing, incoming, now: Optional[datetime] = None) -> str:
    from .copy import time_words
    from .format import station_now

    now = now or station_now()
    return "\n".join([
        f"Ending now: {outgoing.name}, hosted by {outgoing.anchor}. Its promise was: {outgoing.tagline}",
        f"Starting next: {incoming.name}, hosted by {incoming.anchor}. Its promise: {incoming.tagline}",
        f"The time: {time_words(now)}.",
    ])


def story(item_id: int, angle: Optional[str] = None) -> Optional[str]:
    """One story, as its fact sheet (sheets.py)."""
    from .sheets import render_story, sheet_for

    s = sheet_for(item_id)
    return render_story(s, angle=angle) if s else None


def discussion(item_id: int, angle: Optional[str] = None) -> Optional[str]:
    """A story plus what callers will say about it. None with fewer than
    two points: a phone-in with one caller is not a phone-in."""
    from .sheets import render_story, sheet_for

    s = sheet_for(item_id)
    if not s or len(s["sheet"].get("callers") or []) < 2:
        return None
    return render_story(s, with_callers=True, angle=angle)


def _anonymise(text: str) -> str:
    """Drop the `author:` prefix from discussion lines. Handles are public
    on the site, but a radio host reading a username aloud is neither
    useful nor kind."""
    import re

    return re.sub(r"^(- \[[a-z_ ]+\]) [^:\n]{1,40}: ", r"\1 a commenter: ", text, flags=re.M)


def headlines(stories: List[dict], limit: int = 5) -> Optional[str]:
    """The bulletin's stories: title and one line each, in order."""
    from .sheets import cached

    rows = []
    for st in stories[:limit]:
        sheet = (cached(st["item_id"]) or {}).get("sheet") or {}
        rows.append(f'- "{st["title"]}"' + (f"\n  what it is: {sheet['what']}" if sheet.get("what") else ""))
    if len(rows) < 3:
        return None
    return "The stories, in order:\n" + "\n".join(rows)


def front_page(now: Optional[datetime] = None) -> Optional[str]:
    """Readings for the forecast, from the list samples the fetcher keeps:
    arrivals on /new and turnover on /top over the last three hours, and
    what is on top right now."""
    from ..db import repo

    try:
        readings = repo.radio_front_page_readings(hours=3)
    except Exception as e:
        logger.debug(f"radio: no front page readings ({e})")
        return None
    if not readings or not readings.get("samples"):
        return None
    lines = [
        f"New stories arriving: about {readings['new_per_hour']} an hour "
        f"({'faster' if readings['new_trend'] > 0 else 'slower' if readings['new_trend'] < 0 else 'steady'} than earlier).",
        f"Front page turnover: {readings['front_changed']} of thirty places changed hands in the last hour.",
    ]
    if readings.get("top"):
        lines.append("On top right now:")
        lines += [f'- "{t}"' for t in readings["top"][:5]]
    return "\n".join(lines)


def chart(limit: int = 5) -> Optional[str]:
    """The top five by points, listed from five down to one, as the
    countdown reads them. None without a full five."""
    from ..db import repo

    try:
        rows = repo.radio_chart(limit=limit)
    except Exception as e:
        logger.debug(f"radio: no chart ({e})")
        return None
    if len(rows) < limit:
        return None
    import re

    def plain(title: str) -> str:
        # A title is written for the eye: "[pdf]", a dash before the author.
        t = re.sub(r"\s*[\[(](?:pdf|video|audio|\d{4})[\])]\s*", " ", title or "", flags=re.I)
        t = re.sub(r"\s+[–—|]\s+", ", ", t)
        return re.sub(r"\s+", " ", t).strip(" ,")

    out = ["The five highest-scoring stories on Hacker News in the last day:"]
    for pos in range(limit, 0, -1):
        r = rows[pos - 1]
        out.append(f'- Number {pos}: "{plain(r["title"])}" with {r["points"]} points and {r["comments"]} comments.')
    return "\n".join(out)


def for_segment(seg, *, story_id: Optional[int] = None, angle: Optional[str] = None, seed: int = 0, show=None,
                next_show=None, stories: Optional[List[dict]] = None,
                coming_up: Optional[List[str]] = None, now: Optional[datetime] = None) -> Optional[str]:
    """The material for one slot, by what its segment needs."""
    need = seg.needs
    if need == "story":
        return story(story_id, angle) if story_id else None
    if need == "discussion":
        return discussion(story_id, angle) if story_id else None
    if need == "headlines":
        return headlines(stories or [])
    if need == "front_page":
        return front_page(now)
    if need == "chart":
        return chart()
    if need == "trope":
        return trope(seed)
    if need == "jargon":
        return jargon(seed)
    if need == "product":
        return product(seed)
    if need == "stack":
        return stack()
    if need == "show":
        return show_material(show, coming_up, now) if show else None
    if need == "handoff":
        return handoff_material(show, next_show, now) if show and next_show else None
    return ""
