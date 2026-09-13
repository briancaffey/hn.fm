"""The station's library of recurring bits (plans/20).

Short, repeatable features between the briefs: a shout-out to the models in
the stack, a dry one-liner, a two-voice sketch about a tech trope, a jargon
word explained, and the story feature — sixty to ninety seconds on one
story, the station's long form. Each bit is a card: what it is, who reads
it, how long, whether it sits on a bed. The copywriter prompt turns a card
plus its material into radio copy; `speakable()` makes it readable aloud.
"""

import logging
import random
from typing import Dict, List, Optional

from .copy import house_style, speakable

logger = logging.getLogger(__name__)

TASK = "radio.bit"

# key -> the card. `material` names a provider below.
BITS: Dict[str, dict] = {
    "stack": {
        "name": "Under the hood",
        "what": "A warm thirty-second shout-out to the models that make the station: which one writes, "
                "which one speaks, which one makes the music and pictures, and how they hand work to each "
                "other. Proud, plain, a little in awe. Name every model in the material.",
        "host": "ray", "mood": "calm", "words": 80, "bed": True, "material": "stack",
    },
    "joke": {
        "name": "One from Leo",
        "what": "One dry joke or observation about a tech trope — never mean, never about a real person. "
                "Set-up, then the turn. Two or three sentences.",
        "host": "leo", "mood": "neutral", "words": 40, "bed": False, "material": "trope",
    },
    "sketch": {
        "name": "Two engineers",
        "what": "A twenty-second sketch: two engineers, one earnest, one deadpan, on a tech trope. Six to "
                "eight short lines, alternating. Ends on the deadpan one.",
        "host": "mia", "host2": "jason", "mood": "neutral", "words": 90, "bed": False, "material": "trope",
    },
    "word": {
        "name": "Word of the hour",
        "what": "One piece of jargon explained in thirty seconds, for someone smart who never heard it: what "
                "it means, where it came from if that is fun, when you would say it.",
        "host": "sofia", "mood": "calm", "words": 70, "bed": True, "material": "jargon",
    },
    "feature": {
        "name": "The story",
        "what": "Sixty to ninety seconds on one story: what happened, why it matters, the one wrinkle "
                "worth knowing, and what the discussion added if the material has it. A read, not a "
                "summary list; get to the point in the first sentence.",
        "host": "jason", "mood": "calm", "words": 160, "bed": True, "material": "story",
    },
}

TROPES = [
    "it works on my machine", "rewriting it in Rust", "the microservices that became a monolith again",
    "the meeting that could have been an email", "tabs versus spaces", "naming things", "cache invalidation",
    "the todo comment from twenty nineteen", "the demo that only works on the presenter's laptop",
    "adding A.I. to a toaster", "the standup that runs forty minutes", "the one test that is flaky",
    "blaming D.N.S.", "the intern who pushed to main", "the framework of the month",
    "the on-call pager at three in the morning", "the ticket titled 'small fix'", "YAML indentation",
    "the startup that pivots to A.I.", "web scale", "the config file with four hundred options",
]

JARGON = [
    "yak shaving", "bikeshedding", "technical debt", "the happy path", "a race condition", "idempotent",
    "eventual consistency", "a memory leak", "premature optimisation", "rubber duck debugging",
    "the bus factor", "dogfooding", "a heisenbug", "cargo cult programming", "an off-by-one error",
    "the two hard problems", "a hot path", "backpressure", "a thundering herd", "a golden path",
]


def listing() -> str:
    """What the producer sees."""
    return "\n".join(
        f"- {key}: {card['name']} — {card['what'].split('.')[0]}. Read by {card['host']}"
        + (f" and {card['host2']}" if card.get("host2") else "")
        for key, card in BITS.items()
    )


# --- material providers ----------------------------------------------------


def _material_stack() -> str:
    from ..video.title_card import credits_for

    lines = []
    for c in credits_for():
        lines.append(f"- {c['name']}: {', '.join(c['products'])}")
    lines.append("- Nemotron writes the scripts and plans the radio blocks; it runs on a D.G.X. Spark box in the house.")
    lines.append("- Magpie voices every host you hear, each with a mood; Dia is the cloned house voice.")
    lines.append("- ACE-Step makes every music bed from a one-line prompt; FLUX draws the pictures for the videos.")
    lines.append("- Liquidsoap is the D.J. that asks the station what to play next; Icecast sends it to listeners.")
    return "\n".join(lines)


def _material_trope(seed: int) -> str:
    return "Trope: " + TROPES[seed % len(TROPES)]


def _material_jargon(seed: int) -> str:
    return "Term: " + JARGON[seed % len(JARGON)]


def _material_story(item_id: int) -> str:
    from ..db import repo
    from ..digest.compose import _punchline_material
    from ..digest.select import _scraped_material

    item = repo.get_item(item_id)
    if not item:
        return ""
    record = repo.get_latest_story_brief(item_id) or {}
    brief = record.get("brief") or {}
    run = record.get("run") or 1
    summary, excerpt = ("", "") if brief.get("thesis") else _scraped_material(repo, item_id, run)

    class _S:
        pass

    st = _S()
    st.title, st.url, st.brief, st.summary, st.excerpt = item.title, item.url, brief, summary, excerpt
    st.hn_url = f"https://news.ycombinator.com/item?id={item_id}"
    return f'TITLE: "{item.title}"\n' + _punchline_material(st)


def material_for(key: str, story: Optional[int] = None, seed: int = 0) -> str:
    kind = BITS[key]["material"]
    if kind == "stack":
        return _material_stack()
    if kind == "trope":
        return _material_trope(seed)
    if kind == "jargon":
        return _material_jargon(seed)
    if kind == "story" and story:
        return _material_story(story)
    return ""


# --- writing ---------------------------------------------------------------


def write(key: str, story: Optional[int] = None, seed: Optional[int] = None,
          host: Optional[str] = None) -> Optional[dict]:
    """{key, host, host2?, mood, bed, lines: [(host, text), ...]} or None.

    One model call. A single-voice bit is one line; a sketch is several,
    each tagged with who says it. Everything is passed through
    `speakable()` so the voice model reads it the way a person would.
    """
    from ..content.llm_service import LLMService
    from ..content.prompts import render
    from .voice import HOSTS

    card = BITS.get(key)
    if not card:
        return None
    seed = random.randrange(10 ** 6) if seed is None else seed
    material = material_for(key, story=story, seed=seed)
    if card["material"] == "story" and not material:
        return None
    host = host if host in HOSTS else card["host"]
    how = HOSTS.get(host, HOSTS[card["host"]])[2]
    if card.get("host2"):
        how += f"; and {card['host2']}: {HOSTS[card['host2']][2]}"
    try:
        text = LLMService(task=TASK).generate_content(render(
            TASK, house_style=house_style(), words=card["words"], name=card["name"],
            what=card["what"], host=host, how=how, material=material[:5000],
        ))
    except Exception as e:
        logger.warning(f"radio bit {key} failed: {e}")
        return None
    text = (text or "").strip()
    if not text:
        return None

    lines: List[tuple] = []
    if card.get("host2"):
        names = {host.lower(): host, card["host2"].lower(): card["host2"]}
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw or ":" not in raw:
                continue
            who, said = raw.split(":", 1)
            who = who.strip().strip("*").lower()
            if who in names and said.strip():
                lines.append((names[who], speakable(said.strip())))
        if len(lines) < 2:
            return None
    else:
        lines.append((host, speakable(" ".join(text.split()))))
    return {"key": key, "name": card["name"], "host": host, "host2": card.get("host2"),
            "mood": card["mood"], "bed": card["bed"], "lines": lines, "story": story}
