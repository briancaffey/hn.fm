"""Segment types: one spec each, in one place (issue #29).

A segment is something the station airs: a headline, a two-hander, a call
on the comment line. Its spec says what material it needs, what the writer
is asked for, who speaks, how it is mixed and how long it runs. The planner,
the writers' room, the booth and the director all read the spec, so adding
a segment is adding an entry here and nothing else.

`kind` is the coarse class the DJ and the studio page already know
(station_id, brief, feature, bit, music, time_check). `key` is the segment.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Segment:
    key: str
    kind: str
    name: str
    # The assignment, as the writer reads it.
    brief: str = ""
    # What material.py must supply: story, discussion, headlines,
    # front_page, trope, jargon, stack, product, show, handoff, none.
    needs: str = "none"
    # Who speaks: anchor, cohost, cast (rotates), duo (anchor and cohost),
    # callers (anchor plus callers on the phone).
    voices: str = "cast"
    words: int = 60
    # mix.py recipe: plain, bed, phone, sting.
    mix: str = "plain"
    # Which stories qualify: any, show_hn, ask_hn, discussed.
    stories: str = "any"
    # Used when the material is missing: a Show HN slot with no Show HN
    # becomes a headline, not a hole.
    fallback: Optional[str] = None
    # False for what is not written by the writers' room: music, the song
    # (it has its own lyricist), idents from the library, the time.
    written: bool = True
    # How the writer should lay the piece out.
    form: str = "One voice, speaking straight to the listener."


_S = Segment

SEGMENTS: Dict[str, Segment] = {s.key: s for s in (
    # --- imaging -----------------------------------------------------------
    _S("theme", "station_id", "Show open", needs="show", voices="anchor", words=32, mix="sting",
       brief="Open the show. Name the station and the show, give the show's promise in your own "
             "words, and say one thing that is coming up without naming a story you were not given. "
             "Two or three sentences. No 'welcome back', no 'buckle up'."),
    _S("handoff", "station_id", "Handoff", needs="handoff", voices="duo", words=45, mix="bed",
       form="Two voices. The outgoing host, then the incoming host, then one line each. Four lines.",
       brief="The outgoing host hands the station to the next show's host. A sentence of goodbye "
             "that fits the hour, a sentence from the incoming host about what their show is for. "
             "Friendly, brief, in character."),
    _S("ident", "station_id", "Station ID", written=False),
    _S("time_check", "time_check", "Time check", written=False),
    # --- stories -----------------------------------------------------------
    _S("headline", "brief", "Headline", needs="story", voices="cast", words=70, mix="bed",
       brief="Thirty seconds on one story."),
    _S("bulletin", "feature", "The bulletin", needs="headlines", voices="anchor", words=120, mix="sting",
       brief="The top-of-the-hour bulletin: a greeting for the time of day, then each story in one sentence, in the order given, then the station name."),
    _S("two_hander", "feature", "Two-hander", needs="story", voices="duo", words=150, mix="bed",
       stories="discussed", fallback="headline",
       form="Two voices. The first speaker tells the story in four short turns of one or two "
            "sentences. After each, the second speaker answers in twelve words or fewer: a doubt, "
            "a dry remark, or a short question. The second speaker's last line is the objection "
            "from the material, and it is the last line of the piece. Eight turns in all.",
       brief="Two hosts on one story: one tells it, the other is not convinced."),
    _S("comment_line", "feature", "The Comment Line", needs="discussion", voices="callers", words=170,
       mix="phone", stories="discussed", fallback="headline",
       form="The host and two or three callers. The host introduces the story in two sentences "
            "and says the lines are open. Each caller (speaker caller1, caller2, caller3) makes "
            "ONE point from the discussion in their own spoken words, two sentences at most. The "
            "host reacts to each in a sentence and closes.",
       brief="A phone-in on one story. Each caller makes one point, from the material."),
    _S("show_hn", "brief", "Show HN desk", needs="story", voices="cast", words=80, mix="bed",
       stories="show_hn", fallback="headline",
       brief="Someone built something and showed it. What it is, the clever part, and what people asked."),
    _S("ask_hn", "brief", "Ask HN", needs="story", voices="cast", words=80, mix="bed",
       stories="ask_hn", fallback="headline",
       brief="Someone asked the room a question. The question in plain words, then the best answers."),
    # --- the station's own -------------------------------------------------
    _S("forecast", "bit", "Front Page Forecast", needs="front_page", voices="cohost", words=95, mix="bed",
       fallback="word",
       brief="The front page read as a weather forecast, with a straight face, from the readings given."),
    _S("sponsor", "bit", "A word from nobody", needs="product", voices="cast", words=55, mix="bed",
       brief="A mock radio advert for something nobody sells, ending by admitting the station has no sponsors."),
    _S("joke", "bit", "One from Leo", needs="trope", voices="leo", words=40,
       brief="One dry observation about the tech trope in the material. Set-up, then the turn. "
             "Two or three sentences. Never about a real person, never mean."),
    _S("sketch", "bit", "Two engineers", needs="trope", voices="duo", words=90,
       form="Two voices. Six to eight short lines, alternating. Ends on the deadpan one.",
       brief="A twenty-second sketch on the tech trope in the material: two engineers, one "
             "earnest, one deadpan."),
    _S("word", "bit", "Word of the hour", needs="jargon", voices="cohost", words=70, mix="bed",
       brief="One piece of jargon explained for someone smart who never heard it: what it "
             "means, where it came from if that is fun, when you would say it."),
    _S("stack", "bit", "Under the hood", needs="stack", voices="anchor", words=80, mix="bed",
       brief="A shout-out to the models that make the station: which one writes, which one "
             "speaks, which one makes the music. Name every model in the material. Proud, plain, "
             "a little in awe that it works."),
    # --- music -------------------------------------------------------------
    _S("music", "music", "Music", written=False),
    _S("track", "music", "A track", written=False),
    _S("song", "music", "Song of the hour", needs="story", written=False, fallback="music"),
)}

# A "bit" slot in the clock is one of these, in rotation.
BIT_ROTATION: Tuple[str, ...] = ("joke", "word", "sketch", "stack")
# Slots that are filled by a story the planner assigns.
STORY_SEGMENTS = tuple(k for k, s in SEGMENTS.items() if s.needs in ("story", "discussion"))


def segment(key: str) -> Segment:
    return SEGMENTS[key]


def resolve_bit(n: int) -> str:
    """Which bit a "bit" slot is: they rotate by the hour and the slot, so
    the same bit does not open every block."""
    return BIT_ROTATION[n % len(BIT_ROTATION)]


def story_matches(seg: Segment, story: dict) -> bool:
    """Does this candidate qualify for this segment?"""
    title = (story.get("title") or "").lower()
    if seg.stories == "show_hn":
        return title.startswith("show hn")
    if seg.stories == "ask_hn":
        return title.startswith("ask hn")
    if seg.stories == "discussed":
        return bool(story.get("discussed"))
    return True


def listing() -> str:
    """The segment types, as the planner prompt shows them."""
    return "\n".join(f"- {s.key}: {s.name}. {s.brief.split('.')[0]}." for s in SEGMENTS.values()
                     if s.written and s.needs in ("story", "discussion"))
