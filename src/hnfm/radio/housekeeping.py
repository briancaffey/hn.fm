"""Housekeeping: editions that are due, and files that are done (issue #33).

An edition is a block the station makes whether or not anyone is tuned
in, so that the archive has something every day: by default one each
morning, lunchtime and evening. Everything else waits for a listener.
"""

import os
import shutil
import time
from typing import Optional

from . import radio_root
from .format import station_now

SETTING_EDITIONS = "radio.editions_done"
# Blocks keep their files this long after they are made: long enough to be
# repeated when the station is idle, short enough not to fill the disk.
# The archive keeps its own joined copy for as long as it is wanted.
KEEP_BLOCK_DAYS = float(os.getenv("RADIO_KEEP_BLOCK_DAYS", "3"))


def edition_hours() -> list:
    raw = os.getenv("RADIO_EDITION_HOURS", "8,13,19")
    out = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 0 <= int(part) <= 23:
            out.append(int(part))
    return out


def edition_due() -> Optional[str]:
    """"2026-11-12T08" if this hour is an edition hour and its edition has
    not been asked for yet; else None."""
    from ..db import repo

    now = station_now()
    if now.hour not in edition_hours():
        return None
    key = now.strftime("%Y-%m-%dT%H")
    done = repo.get_setting(SETTING_EDITIONS, []) or []
    return None if key in done else key


def mark_edition(key: str) -> None:
    from ..db import repo

    done = (repo.get_setting(SETTING_EDITIONS, []) or [])[-30:]
    repo.set_setting(SETTING_EDITIONS, done + [key])


def prune_blocks() -> int:
    """Remove block directories older than KEEP_BLOCK_DAYS, and booth
    leftovers older than an hour. Returns how many directories went."""
    removed = 0
    now = time.time()
    for sub, max_age in (("blocks", KEEP_BLOCK_DAYS * 86400), ("tmp", 3600)):
        root = os.path.join(radio_root(), sub)
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            path = os.path.join(root, name)
            try:
                if os.path.isdir(path) and now - os.path.getmtime(path) > max_age:
                    shutil.rmtree(path, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
    return removed
