"""The bank: material the station keeps ready (plans/20).

Two kinds of stock. Generic: station IDs in every host's voice, time
checks are made on demand, and a handful of music beds — enough that the
director always has something to play between episodes without waiting on
a model. Block-specific: the lines the producer wrote for one run sheet,
voiced right after the sheet is planned so they exist by the time they are
needed. Anything not ready in time is substituted from the generic stock.
"""

import logging
import os
import uuid
from typing import Dict, List, Optional

from . import log, radio_root
from .library import add_to_bank, bank_counts, bank_dir, load_bank, safety_path, to_mp3
from .music import STYLES, make_bed
from .producer import STATION_IDS
from .voice import HOSTS, say

logger = logging.getLogger(__name__)

# How much generic stock to keep.
TARGETS = {"station_id": 10, "music": 8}
# Generic beds are short: the station changes topic every half minute.
BED_SECONDS = int(os.getenv("RADIO_BED_SECONDS", "35"))


def _new_path(kind: str) -> str:
    return os.path.join(bank_dir(), f"{kind}_{uuid.uuid4().hex[:10]}.mp3")


def fill(targets: Optional[Dict[str, int]] = None, max_new: int = 6) -> Dict[str, int]:
    """Top the generic stock up to the targets. Returns what was made.

    Capped per call so a beat tick never runs the TTS or music service for
    long; the next tick continues.
    """
    targets = targets or TARGETS
    have = bank_counts()
    made: Dict[str, int] = {}
    budget = max_new

    hosts = [h for h in HOSTS if h != "dia"]
    n = 0
    while budget and have.get("station_id", 0) < targets["station_id"]:
        line = STATION_IDS[n % len(STATION_IDS)]
        host = hosts[n % len(hosts)]
        path = say(line, host, _new_path("station_id"), mood="calm")
        n += 1
        if not path:
            break
        add_to_bank({"id": uuid.uuid4().hex[:12], "kind": "station_id", "path": path,
                     "text": line, "host": host})
        log("bank", f"recorded a station ID in {host}'s voice: “{line}”", kind="station_id", host=host)
        have["station_id"] = have.get("station_id", 0) + 1
        made["station_id"] = made.get("station_id", 0) + 1
        budget -= 1

    n = have.get("music", 0)
    while budget and have.get("music", 0) < targets["music"]:
        style = STYLES[n % len(STYLES)]
        log("bank", f"prompting the jukebox: {style}", kind="music", prompt=style)
        path = make_bed(style, BED_SECONDS, _new_path("music"))
        n += 1
        if not path:
            break
        add_to_bank({"id": uuid.uuid4().hex[:12], "kind": "music", "path": path,
                     "style": style, "seconds": BED_SECONDS})
        log("bank", f"pressed a {BED_SECONDS}-second music bed: {style[:50]}", kind="music")
        have["music"] = have.get("music", 0) + 1
        made["music"] = made.get("music", 0) + 1
        budget -= 1

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


def voice_sheet(sheet_id: str, items: List[dict]) -> int:
    """Make the block's spoken items: the lines the producer wrote, and the
    briefs on new stories (written from the story, then read over a quiet
    bed). Returns how many were made."""
    from .briefs import brief_for, spoken
    from .library import pick_from_bank

    spoken_kinds = ("station_id", "coming_up", "time_check", "brief")
    todo = [it for it in items if it.get("kind") in spoken_kinds and (it.get("line") or it.get("kind") == "brief")]
    log("bank", f"voicing {len(todo)} items for the block", sheet_id=sheet_id)
    made = 0
    beds = [b for b in load_bank() if b["kind"] == "music" and not b.get("sheet_id")]
    for idx, it in enumerate(items):
        kind = it.get("kind")
        if kind not in spoken_kinds:
            continue
        host = it.get("host") or "mia"
        mood = it.get("mood") or "calm"
        if kind == "brief":
            b = brief_for(int(it["story"])) if it.get("story") else None
            if not b:
                log("bank", f"no brief could be written for story {it.get('story')}; skipped", kind="brief")
                continue
            text = spoken(b)
            bed = beds[(idx * 7) % len(beds)]["path"] if beds else None
            path = say(text, host, _new_path("brief"), mood=mood, bed=bed)
            if not path:
                continue
            add_to_bank({"id": f"{sheet_id}-{idx}", "kind": "brief", "path": path,
                         "text": b["title"], "host": host, "sheet_id": sheet_id,
                         "story": int(it["story"]), "mood": mood})
            log("bank", f"{host} ({mood}) read a brief on: {b['title'][:60]}", kind="brief", host=host,
                sheet_id=sheet_id, story=int(it["story"]))
            made += 1
            continue
        if not it.get("line"):
            continue
        path = say(it["line"], host, _new_path(kind), mood=mood)
        if not path:
            continue
        add_to_bank({"id": f"{sheet_id}-{idx}", "kind": kind, "path": path,
                     "text": it["line"], "host": host, "sheet_id": sheet_id, "mood": mood})
        log("bank", f"{host} ({mood}) recorded: “{it['line'][:70]}”", kind=kind, host=host, sheet_id=sheet_id)
        made += 1
    return made


def prune(keep_sheets: List[str], keep_generic: int = 40) -> int:
    """Drop block lines for sheets that are gone, and cap the generic stock."""
    items = load_bank()
    keep, dropped = [], 0
    generic = 0
    for i in sorted(items, key=lambda i: i.get("created_at") or "", reverse=True):
        if i.get("sheet_id"):
            if i["sheet_id"] in keep_sheets:
                keep.append(i)
                continue
        else:
            generic += 1
            if generic <= keep_generic:
                keep.append(i)
                continue
        dropped += 1
        try:
            os.unlink(i["path"])
        except OSError:
            pass
    if dropped:
        from .library import save_bank

        save_bank(keep)
    return dropped
