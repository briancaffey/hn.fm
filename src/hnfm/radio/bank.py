"""The bank: imaging and music the station keeps ready (issue #31).

Stock, per show: beds in the show's palette, a couple of sung jingles in
its style, spoken station IDs from its hosts, and sweepers from the
announcer. Kept ahead of need so
the air never waits on the music model. The current show is stocked
first, then the one after it; a show at four in the morning is not
stocked at noon.

Nothing written for one block is here. That lives with the block.
"""

import logging
import os
import uuid
from typing import Dict, List, Optional

from . import log, radio_root
from .format import SHOWS, Show, show_at, station_now
from .library import add_to_bank, bank_counts, bank_dir, load_bank, safety_path, save_bank, to_mp3
from .music import make_bed, make_song
from .voice import say

logger = logging.getLogger(__name__)

# What each show should have on the shelf.
PER_SHOW = {"music": int(os.getenv("RADIO_BEDS_PER_SHOW", "4")),
            "track": int(os.getenv("RADIO_TRACKS_PER_SHOW", "6")),
            "jingle": int(os.getenv("RADIO_JINGLES_PER_SHOW", "2")),
            "station_id": 3, "sweeper": 3}
BED_SECONDS = int(os.getenv("RADIO_BED_SECONDS", "40"))
# A track is a piece of music in its own right, between the talk.
TRACK_SECONDS = int(os.getenv("RADIO_TRACK_SECONDS", "120"))
JINGLE_SECONDS = 10
KINDS = ("music", "track", "station_id", "sweeper", "jingle")

STATION_IDS = [
    "You're listening to H.N.F.M.",
    "This is H.N.F.M. Hacker News, on the radio.",
    "H.N.F.M. Made by machines, about what people are building.",
    "You're on H.N.F.M., where the comment section gets a voice.",
    "H.N.F.M. Nobody is in the building.",
    "Stay where you are. This is H.N.F.M.",
]

# What the announcer says between two effects.
SWEEPERS = [
    "{name}. On H.N.F.M.",
    "H.N.F.M. {tagline}",
    "No ads. No building. No people. H.N.F.M.",
    "This is {name}.",
    "Hacker News. Out loud. H.N.F.M.",
]

# What a jingle sings. Short lines the music model can land in ten seconds.
JINGLE_LYRICS = [
    "[chorus]\nH N F M\n{name}",
    "[chorus]\n{name}\nOn H N F M",
    "[chorus]\nH N F M\nHacker News on the radio",
]


def _new_path(kind: str) -> str:
    return os.path.join(bank_dir(), f"{kind}_{uuid.uuid4().hex[:10]}.mp3")


def _order() -> List[Show]:
    """Shows in the order they need stock: on air now, then up next, then
    the rest of the day."""
    now = station_now()
    i = SHOWS.index(show_at(now))
    return [SHOWS[(i + k) % len(SHOWS)] for k in range(len(SHOWS))]


def wanted() -> List[tuple]:
    """(show, kind) for each missing item, most urgent first."""
    out = []
    for kind in KINDS:
        for sh in _order()[:2]:
            have = bank_counts(sh.key).get(kind, 0)
            out += [(sh, kind)] * max(0, PER_SHOW[kind] - have)
    for sh in _order()[2:]:
        for kind in KINDS:
            have = bank_counts(sh.key).get(kind, 0)
            out += [(sh, kind)] * max(0, PER_SHOW[kind] - have)
    return out


def _make(sh: Show, kind: str) -> Optional[dict]:
    n = bank_counts(sh.key).get(kind, 0)
    if kind == "music":
        style = sh.palette[n % len(sh.palette)]
        log("bank", f"asking the jukebox for a {sh.name} bed: {style[:60]}", kind="music", show=sh.key)
        path = make_bed(style, BED_SECONDS, _new_path("music"))
        return path and {"kind": "music", "path": path, "style": style, "seconds": BED_SECONDS}
    if kind == "track":
        style = sh.palette[(n + 1) % len(sh.palette)]
        log("bank", f"asking the jukebox for a {sh.name} track: {style[:60]}", kind="music", show=sh.key)
        path = make_song(style, "[instrumental]", TRACK_SECONDS, _new_path("track"), fade=4.0)
        return path and {"kind": "track", "path": path, "style": style, "seconds": TRACK_SECONDS}
    if kind == "jingle":
        lyrics = JINGLE_LYRICS[n % len(JINGLE_LYRICS)].format(name=sh.name)
        style = f"radio station jingle, {sh.song_style}, short, catchy, vocal harmonies"
        log("bank", f"asking the jukebox to sing a {sh.name} jingle", kind="jingle", show=sh.key)
        path = make_song(style, lyrics, JINGLE_SECONDS, _new_path("jingle"), fade=0.8)
        return path and {"kind": "jingle", "path": path, "style": style, "text": lyrics.replace("[chorus]\n", ""),
                         "seconds": JINGLE_SECONDS}
    if kind == "sweeper":
        from .booth import imaging

        line = SWEEPERS[(n + SHOWS.index(sh)) % len(SWEEPERS)].format(name=sh.name, tagline=sh.tagline)
        path = imaging(line, _new_path("sweeper"))
        from . import mix

        return path and {"kind": "sweeper", "path": path, "text": line, "host": "announcer",
                         "seconds": (mix.measure(path) or {}).get("seconds")}
    if kind == "station_id":
        line = STATION_IDS[(n + SHOWS.index(sh)) % len(STATION_IDS)]
        host = (sh.anchor, sh.cohost, *sh.cast)[n % (2 + len(sh.cast))]
        path = say(line, host, _new_path("station_id"))
        return path and {"kind": "station_id", "path": path, "text": line, "host": host}
    return None


def stock(sh: Show, max_new: int = 20) -> Dict[str, int]:
    """Stock one show's shelf, whatever the time of day: for an edition
    made ahead of its show."""
    made: Dict[str, int] = {}
    for kind in KINDS:
        while sum(made.values()) < max_new and bank_counts(sh.key).get(kind, 0) < PER_SHOW[kind]:
            item = _make(sh, kind)
            if not item:
                break
            add_to_bank({"id": uuid.uuid4().hex[:12], "show": sh.key, **item})
            made[kind] = made.get(kind, 0) + 1
    if made:
        log("bank", f"stocked {sh.name}: " + ", ".join(f"{n} {k}" for k, n in made.items()), show=sh.key)
    ensure_safety()
    return made


def fill(max_new: int = 6) -> Dict[str, int]:
    """Make up to `max_new` missing items, most urgent first. Capped so a
    beat tick never holds the music model for long; the next tick goes on."""
    made: Dict[str, int] = {}
    failed = set()
    for sh, kind in wanted():
        if sum(made.values()) >= max_new:
            break
        if kind in failed:
            continue  # that model is away; do not ask it five more times
        item = _make(sh, kind)
        if not item:
            failed.add(kind)
            continue
        add_to_bank({"id": uuid.uuid4().hex[:12], "show": sh.key, **item})
        log("bank", f"stocked a {kind.replace('_', ' ')} for {sh.name}", kind=kind, show=sh.key)
        made[kind] = made.get(kind, 0) + 1
    ensure_safety()
    return made


def ensure_safety() -> Optional[str]:
    """The file Liquidsoap loops when everything else has failed: the first
    music bed in the bank, copied to a fixed path the script knows."""
    dst = safety_path()
    if os.path.exists(dst):
        return dst
    beds = [i for i in load_bank() if i["kind"] == "music"]
    if not beds:
        return None
    os.makedirs(radio_root(), exist_ok=True)
    return dst if to_mp3(beds[0]["path"], dst, loudnorm=False) else None


def prune(keep_per_show: int = 12) -> int:
    """Cap the stock per show and kind, oldest out first."""
    items = sorted(load_bank(), key=lambda i: i.get("created_at") or "", reverse=True)
    keep, seen, dropped = [], {}, 0
    for i in items:
        key = (i.get("show"), i["kind"])
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= keep_per_show:
            keep.append(i)
            continue
        dropped += 1
        try:
            os.unlink(i["path"])
        except OSError:
            pass
    if dropped:
        save_bank(keep)
    return dropped
