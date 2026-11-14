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

ASK = """You score a short narrated news video. Pick the one mood that fits the story best.
Reply with one JSON object and nothing else: {"mood": "<one of the names below>"}
"""

# Code owns the sound, the model picks the feeling: asked for a free tag
# line, the local model scored a story about a discovery as a "mournful
# trombone drone". Every bed here sits under a voice: no vocals, no drums
# that fight speech, a steady middle tempo.
MOODS = {
    "discovery": "music box, pizzicato strings and warm felt piano, curious and wondering, 96 bpm, light and bright",
    "playful": "plucked ukulele, glockenspiel and soft claps, whimsical and bouncy, 104 bpm, cheerful",
    "momentum": "pulsing analog synth arpeggio, soft kick, driving and optimistic, 112 bpm, modern documentary",
    "tension": "low cello ostinato and ticking clock percussion, suspenseful but restrained, 90 bpm",
    "reflective": "solo felt piano with soft string pad, thoughtful and warm, 76 bpm, gentle",
    "triumph": "warm brass swells over strings and timpani rolls, uplifting and proud, 92 bpm, cinematic",
}
FALLBACK = MOODS["discovery"]


def choose(brief: Dict) -> str:
    message = "Score this video.\n\n```json\n" + json.dumps({
        "story": brief["title"], "summary": (brief.get("summary") or "")[:300],
        "opening line": (brief["scenes"][0]["text"] if brief.get("scenes") else ""),
        "moods": {k: v.split(",")[-2].strip() + "; " + v.split(",")[0] for k, v in MOODS.items()}}, indent=1) + "\n```"
    try:
        got = hermes.ask(message, instructions=ASK, session=f"hnfm-music-{brief['item_id']}-{brief['run']}", timeout=90)
        m = re.search(r"\{.*\}", got["text"] or "", re.S)
        mood = str(json.loads(m.group(0)).get("mood") or "").strip().lower() if m else ""
        if mood in MOODS:
            return MOODS[mood]
    except (hermes.AgentError, ValueError) as e:
        logger.info(f"music mood: {e}")
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
