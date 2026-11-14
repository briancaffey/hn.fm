"""A music bed for a story video, chosen by Hermes and played by ACE-Step.

The agent names the mood in a short tag line (instruments, feel, tempo);
the music model on the spark box plays an instrumental of the video's
length. The kit lays it well under the narration. No bed, no failure: the
video is made without one.
"""

import json
import logging
import os
import re
from typing import Dict

from . import hermes

logger = logging.getLogger(__name__)

ASK = """You score a short narrated news video. Reply with one JSON object and nothing else:
{"music": "<a tag line for an instrumental bed>"}
The tag line is 6 to 16 words: instruments, mood, tempo in bpm. It sits under a voice, so: calm,
no vocals, nothing that competes with speech. Match the story's subject and the film's art style."""

FALLBACK = "warm felt piano and soft strings, curious and gentle, 84 bpm, instrumental"


def choose(brief: Dict) -> str:
    message = "Score this video.\n\n```json\n" + json.dumps({
        "story": brief["title"], "summary": (brief.get("summary") or "")[:300],
        "art style": brief.get("theme"), "seconds": brief["seconds"]}, indent=1) + "\n```"
    try:
        got = hermes.ask(message, instructions=ASK, session=f"hnfm-music-{brief['item_id']}-{brief['run']}", timeout=90)
        m = re.search(r"\{.*\}", got["text"] or "", re.S)
        line = str(json.loads(m.group(0)).get("music") or "").strip() if m else ""
        if 5 <= len(line.split()) <= 20 and "vocal" not in line.lower().replace("no vocals", ""):
            return line
    except (hermes.AgentError, ValueError) as e:
        logger.info(f"music line: {e}")
    return FALLBACK


def make(brief: Dict, folder: str) -> Dict:
    from ..radio.music import make_bed

    style = choose(brief)
    out = os.path.join(folder, "music.mp3")
    try:
        got = make_bed(style, int(brief["seconds"]) + 1, out)
    except Exception as e:
        got = None
        logger.warning(f"music bed: {e}")
    if got and os.path.exists(out):
        brief["music_path"] = out
        return {"style": style, "ok": True}
    return {"style": style, "ok": False}
