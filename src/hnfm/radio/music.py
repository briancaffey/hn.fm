"""Music from ACE-Step: beds, jingles and songs (issue #31).

Two ways in. A bed is instrumental and comes from the chat endpoint the
pipeline already uses. Anything sung — a jingle, the song of the hour —
goes through the task endpoint, which takes lyrics and a duration. Both
come back as a whole piece and are trimmed, faded and levelled here.
"""

import logging
import os
import time
from typing import Optional

from .library import to_mp3

logger = logging.getLogger(__name__)

# Styles for a show with no palette of its own (there is none; this is the
# floor for a bed asked for by style alone).
STYLES = [
    "warm lo-fi piano with soft vinyl crackle, 72 bpm, instrumental",
    "bright synth arpeggios and a steady kick, 110 bpm, instrumental",
    "acoustic guitar and brushed drums, easy tempo, instrumental",
    "ambient pads with a slow bass pulse, 60 bpm, instrumental",
    "jazzy Rhodes and upright bass, late night, 84 bpm, instrumental",
    "clean electric guitar over a light beat, hopeful, 96 bpm, instrumental",
]


def _base() -> str:
    return os.getenv("ACESTEP_BASE_URL", "http://host.docker.internal:8015").rstrip("/")


def make_bed(style: str, seconds: int, out_mp3: str) -> Optional[str]:
    """An instrumental of exactly `seconds`. Through the task endpoint,
    which takes a duration: the chat endpoint chose its own length, and a
    forty-second bed came back as twenty."""
    seconds = max(20, min(int(seconds or 40), 150))
    return make_song(f"{style}, no vocals", "[instrumental]", seconds, out_mp3, fade=2.5)


def make_song(style: str, lyrics: str, seconds: int, out_mp3: str, fade: float = 2.0) -> Optional[str]:
    """Something sung: `style` is a tag line, `lyrics` carry [verse] and
    [chorus] marks. One task on the music model, polled until it is done."""
    import json

    import requests

    from ..audio.music_service import _ensure_initialized

    if not _ensure_initialized():
        return None
    seconds = max(6, min(int(seconds or 60), 150))
    try:
        r = requests.post(f"{_base()}/release_task", timeout=60, json={
            "prompt": style, "lyrics": lyrics, "audio_duration": seconds, "inference_steps": 8,
            "audio_format": "mp3", "task_type": "text2music", "vocal_language": "en",
            "use_random_seed": True,
        })
        task_id = ((r.json() or {}).get("data") or {}).get("task_id")
        if not task_id:
            logger.warning(f"radio music: no task id ({r.status_code}: {r.text[:120]})")
            return None
        deadline = time.time() + int(os.getenv("MUSIC_TIMEOUT_SECONDS", "240"))
        file_url = None
        while time.time() < deadline:
            time.sleep(2.5)
            q = requests.post(f"{_base()}/query_result", json={"task_id_list": [task_id]}, timeout=30).json()
            row = ((q or {}).get("data") or [{}])[0]
            if row.get("status") == 2:
                logger.warning("radio music: the task failed")
                return None
            if row.get("status") == 1:
                result = row.get("result")
                result = json.loads(result) if isinstance(result, str) else result
                file_url = (result or [{}])[0].get("file")
                break
        if not file_url:
            logger.warning("radio music: timed out waiting for the song")
            return None
        audio = requests.get(f"{_base()}{file_url}", timeout=120)
        if audio.status_code != 200 or len(audio.content) < 2000:
            return None
    except Exception as e:
        logger.warning(f"radio music: song failed ({e})")
        return None
    tmp = out_mp3 + ".src.mp3"
    os.makedirs(os.path.dirname(out_mp3) or ".", exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(audio.content)
    try:
        return out_mp3 if to_mp3(tmp, out_mp3, seconds=seconds, fade=fade) else None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
