"""HNFM on air — the internet radio station.

Off by default. `enabled()` is the one switch the API, the beat table and
the UI all consult; when it is false nothing here runs, nothing is exposed,
and nothing is required. README.md is the operator's page.

What a block is, and who decides it:
    format.py       the day's shows and the shape of each quarter hour (code)
    segments.py     one spec per segment type: material, voices, mix, length
    planner.py      stories into the story slots: one model call, checked

How a block is made:
    sheets.py       a fact sheet per story, made once and kept
    material.py     what each segment is written from
    writers.py      draft, rules, editor, rewrite, repair
    booth.py        speak each line, listen back, join, mix
    mix.py          the mix recipes, as ffmpeg graphs
    qa.py           the listen-back: transcript match and levels
    voice.py        hosts and callers; every spoken line cached by content
    music.py        beds, tracks, jingles and songs from the music model
    production.py   runs all of the above over a planned block
    archive.py      each finished block as one file, and the podcast feed

How it gets to air:
    bank.py         stock per show: beds, tracks, jingles, station IDs
    library.py      the stock shelf and finished episodes
    director.py     what plays next; produces only for a listener
    housekeeping.py editions that are due, files that are done
    radio.liq       the Liquidsoap script (served by the API, run by the DJ)
"""

import os


def enabled() -> bool:
    return os.getenv("RADIO_ENABLED", "false").strip().lower() == "true"


def radio_root() -> str:
    """Where the station keeps its own files under outputs/."""
    return os.path.join(os.getenv("OUTPUTS_DIR", "/app/outputs"), "radio")


def log(component: str, message: str, **meta) -> None:
    """A line of the station's running commentary, for the studio (plans/21).

    Never raises: the commentary must not be able to stop the show.
    """
    try:
        from ..db import repo

        repo.radio_log_write(component, message, meta or None)
    except Exception:
        pass

