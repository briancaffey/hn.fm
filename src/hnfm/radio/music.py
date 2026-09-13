"""A music bed of a given length (plans/20).

ACE-Step on the inference cluster returns a whole piece; the station wants
45 to 90 seconds at broadcast loudness with a clean fade. Generation is the
slow part (a minute or so), which is why the bank keeps beds ready and the
producer only picks styles.
"""

import logging
import os
import tempfile
from typing import Optional

from .library import to_mp3

logger = logging.getLogger(__name__)

# Styles the fallback producer rotates through; the LLM producer writes its
# own briefs in the same register.
STYLES = [
    "warm lo-fi piano with soft vinyl crackle, 72 bpm, instrumental",
    "bright synth arpeggios and a steady kick, 110 bpm, instrumental",
    "acoustic guitar and brushed drums, easy tempo, instrumental",
    "ambient pads with a slow bass pulse, 60 bpm, instrumental",
    "jazzy Rhodes and upright bass, late night, 84 bpm, instrumental",
    "clean electric guitar over a light beat, hopeful, 96 bpm, instrumental",
]


def make_bed(style: str, seconds: int, out_mp3: str) -> Optional[str]:
    from ..audio.music_service import generate_music_bed

    seconds = max(30, min(int(seconds or 60), 120))
    prompt = f"{style}. No vocals. A radio music bed, {seconds} seconds."
    tmp = os.path.join(tempfile.gettempdir(), f"radio_bed_{os.getpid()}_{abs(hash(style)) % 10**6}.wav")
    try:
        if not generate_music_bed(prompt, tmp):
            return None
        return out_mp3 if to_mp3(tmp, out_mp3, seconds=seconds, fade=2.5) else None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
