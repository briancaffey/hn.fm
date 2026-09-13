"""HNFM on air — the internet radio station (plans/20).

Off by default. `enabled()` is the one switch the API, the beat table and
the UI all consult; when it is false nothing here runs, nothing is exposed,
and nothing is required.

    schemas.py    the run sheet: what a block of programming is
    library.py    what is playable — finished episodes, the interstitial bank
    producer.py   plans a block: one LLM call, or the deterministic fallback
    director.py   serves the next item to Liquidsoap; queue, history, replans
    voice.py      speaks a line in a host's voice (Magpie or Dia) to MP3
    music.py      a music bed of a given length from ACE-Step
    bank.py       keeps generic station IDs, time checks and beds ready
    radio.liq     the Liquidsoap script (served by the API, run by the DJ)
    README.md     the operator's page: what is exposed, how to turn it on
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

