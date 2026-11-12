"""The format: what the station is at any hour, and the shape of that hour.

The code owns the shape; the model owns the choices (issue #28). A day is
six shows. Each has its hosts, a tone the writers are told about, a music
palette, and a clock: four quarters, each an ordered list of slots. A slot
names a segment type from `segments.py`. Nothing here calls a model or
reads the database, so the shape of any hour can be printed, tested and
argued about.

A block is one quarter. Quarters are taken in order, not from the wall
clock: a quarter runs about ten minutes, so an hour that follows the wall
clock would open the show three times. The first block of each hour is the
quarter with the show open and the bulletin; the rest follow and repeat.

    show_at(now)                 which show is on
    next_quarter(last, now)      which quarter comes next
    rundown(now, quarter)        the slots of that block, in order
    schedule()                   the day, for the listen page
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def station_tz():
    """The station keeps one clock. A time check that is right in UTC is
    wrong in the kitchen."""
    name = os.getenv("RADIO_TZ", "America/New_York")
    try:
        return ZoneInfo(name) if ZoneInfo else None
    except Exception:
        return None


def station_now() -> datetime:
    tz = station_tz()
    return datetime.now(tz) if tz else datetime.now()


@dataclass(frozen=True)
class Show:
    key: str
    name: str
    start: int                 # hour it begins, station time
    end: int                   # hour it ends (exclusive); may wrap midnight
    anchor: str                # leads; reads the idents and the handoffs
    cohost: str                # the second voice in two-handers
    cast: Tuple[str, ...]      # who else may read a headline
    tagline: str               # said on air
    tone: str                  # told to the writers, never read out
    palette: Tuple[str, ...]   # music beds, as style prompts
    song_style: str            # the song of the hour, as style tags
    clock: Tuple[Tuple[str, ...], ...]   # four quarters, each a tuple of slots

    def hours(self) -> List[int]:
        h, out = self.start, []
        while h != self.end:
            out.append(h)
            h = (h + 1) % 24
        return out


# Slot names are segment keys (segments.py). "music" is a short bed from
# the show's palette, "track" a full piece of music, "ident" a station ID
# (sung when the shelf has a jingle), "sweeper" the announcer between two
# effects, "cold_open" a teaser cut from the block's own pieces.
_DAY = (
    ("cold_open", "theme", "bulletin", "headline", "headline", "music", "two_hander", "track"),
    ("sweeper", "headline", "comment_line", "music", "bit", "correspondent", "sponsor", "track"),
    ("ident", "time_check", "headline", "show_hn", "music", "forecast", "headline", "track"),
    ("sweeper", "chart", "headline", "ask_hn", "music", "headline", "song", "ident"),
)
# The small hours: fewer words, more music. Nobody is asking for a bulletin
# at four in the morning, and the models have other work.
_NIGHT = (
    ("cold_open", "theme", "time_check", "headline", "track", "two_hander", "track"),
    ("sweeper", "headline", "music", "bit", "track", "correspondent", "track"),
    ("ident", "time_check", "comment_line", "track", "headline", "track"),
    ("sweeper", "headline", "chart", "track", "song", "ident"),
)


SHOWS: Tuple[Show, ...] = (
    Show(
        key="cold_start", name="Cold Start", start=6, end=10,
        anchor="mia", cohost="leo", cast=("sofia", "aria"),
        tagline="Everything that shipped while you slept.",
        tone="Morning. Bright, quick, a little under-caffeinated. Short items, forward motion.",
        palette=(
            "bright acoustic guitar and handclaps, sunny, 112 bpm, instrumental",
            "upbeat synth pop with a bouncing bass, optimistic, 118 bpm, instrumental",
            "light funk guitar and tight drums, morning energy, 104 bpm, instrumental",
            "marimba and plucked strings, playful, 108 bpm, instrumental",
        ),
        song_style="sunny indie pop, jangly guitars, female lead vocal, handclaps, 116 bpm",
        clock=_DAY,
    ),
    Show(
        key="main_thread", name="Main Thread", start=10, end=14,
        anchor="sofia", cohost="jason", cast=("aria", "mia"),
        tagline="The working day, one story at a time.",
        tone="Midday. A newsroom at work: exact, brisk, unfussy.",
        palette=(
            "driving electronic pulse with clean piano stabs, newsroom, 120 bpm, instrumental",
            "minimal techno with a warm bassline, focused, 122 bpm, instrumental",
            "string ostinato over soft electronic drums, purposeful, 110 bpm, instrumental",
            "clean electric piano and a steady kick, confident, 114 bpm, instrumental",
        ),
        song_style="synthwave, driving bass, male lead vocal, anthemic chorus, 118 bpm",
        clock=_DAY,
    ),
    Show(
        key="the_diff", name="The Diff", start=14, end=18,
        anchor="aria", cohost="leo", cast=("jason", "sofia"),
        tagline="What changed, and who is arguing about it.",
        tone="Afternoon. Opinionated, and fond of an argument in the comment section.",
        palette=(
            "lo-fi hip hop beat with dusty keys, head-nodding, 86 bpm, instrumental",
            "funk bass and wah guitar, loose, 98 bpm, instrumental",
            "boom bap drums with a jazz sample feel, 90 bpm, instrumental",
            "mellow trip hop with vinyl crackle, 82 bpm, instrumental",
        ),
        song_style="funk, slap bass, horn section, soulful female vocal, 102 bpm",
        clock=_DAY,
    ),
    Show(
        key="show_and_tell", name="Show and Tell", start=18, end=22,
        anchor="mia", cohost="ray", cast=("aria", "leo"),
        tagline="People made things. Here they are.",
        tone="Evening. Warm, curious about the people who make things. Generous, never gushing.",
        palette=(
            "warm Rhodes piano and brushed drums, evening, 88 bpm, instrumental",
            "fingerpicked acoustic guitar with soft upright bass, 84 bpm, instrumental",
            "indie folk with glockenspiel and gentle percussion, 96 bpm, instrumental",
            "soul groove with organ and clean guitar, relaxed, 92 bpm, instrumental",
        ),
        song_style="indie folk, acoustic guitar, warm male vocal, close harmonies, 94 bpm",
        clock=_DAY,
    ),
    Show(
        key="night_shift", name="Night Shift", start=22, end=2,
        anchor="ray", cohost="jason", cast=("sofia",),
        tagline="Slower stories for a quieter hour.",
        tone="Late night. Unhurried and thoughtful, with room between the sentences.",
        palette=(
            "late night jazz trio, upright bass and brushes, smoky, 72 bpm, instrumental",
            "ambient pads with a slow bass pulse, deep, 60 bpm, instrumental",
            "muted trumpet over soft piano chords, nocturne, 66 bpm, instrumental",
            "downtempo electronica with warm tape hiss, 78 bpm, instrumental",
        ),
        song_style="slow jazz ballad, upright bass, brushed drums, deep male vocal, 70 bpm",
        clock=_NIGHT,
    ),
    Show(
        key="garbage_collection", name="Garbage Collection", start=2, end=6,
        anchor="leo", cohost="sofia", cast=("ray",),
        tagline="The stories nobody else picked up.",
        tone="The small hours. Dry, sparse, a little strange, as if read to an empty building.",
        palette=(
            "dub techno chords with deep reverb, hypnotic, 110 bpm, instrumental",
            "slow modular synth arpeggio, sparse, 64 bpm, instrumental",
            "ambient guitar swells and field recording texture, 58 bpm, instrumental",
            "minimal piano with long reverb tails, 56 bpm, instrumental",
        ),
        song_style="dream pop, washed out guitars, breathy female vocal, slow, 76 bpm",
        clock=_NIGHT,
    ),
)

_BY_KEY = {s.key: s for s in SHOWS}


def show(key: str) -> Optional[Show]:
    return _BY_KEY.get(key)


def show_at(now: Optional[datetime] = None) -> Show:
    hour = (now or station_now()).hour
    for s in SHOWS:
        if hour in s.hours():
            return s
    return SHOWS[0]  # unreachable while the shows cover the day


@dataclass(frozen=True)
class Slot:
    index: int
    segment: str      # a key in segments.SEGMENTS
    show: str         # show key
    quarter: int      # 0..3


def hour_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H")


def next_quarter(last: Optional[dict], now: Optional[datetime] = None) -> int:
    """Which quarter the next block is. `last` is {"hour": hour_key,
    "quarter": n} for the block planned before this one, or None.

    A new hour starts at quarter 0 (the show open and the bulletin). Within
    an hour the quarters follow in order; if the hour is not over after
    the fourth, they go round again from the second, so the show is opened
    once an hour however fast the blocks play.
    """
    now = now or station_now()
    if not last or last.get("hour") != hour_key(now):
        return 0
    q = int(last.get("quarter", -1)) + 1
    return q if q <= 3 else 1 + (q - 1) % 3


def rundown(now: Optional[datetime] = None, quarter: int = 0) -> List[Slot]:
    """The slots of one block: quarter `quarter` of the show on air."""
    now = now or station_now()
    s = show_at(now)
    q = max(0, min(int(quarter), len(s.clock) - 1))
    return [Slot(index=n, segment=seg, show=s.key, quarter=q) for n, seg in enumerate(s.clock[q])]


def schedule(now: Optional[datetime] = None) -> List[dict]:
    """The day's shows in air order starting at six, with the one on now."""
    on = show_at(now).key
    return [{
        "key": s.key, "name": s.name, "start": s.start, "end": s.end,
        "anchor": s.anchor, "cohost": s.cohost, "tagline": s.tagline,
        "on_air": s.key == on,
    } for s in SHOWS]
