"""Cover art: one picture per show and one for the station (issue #43).

Drawn by the image model from a fixed prompt, kept under `art/`, and used
on the listen page, in the podcast feed and as the still behind an
edition's video. The house style is one sentence shared by every prompt,
so the six shows look like one station.

    path(key)     the picture for a show key or "station", if it exists
    draw(key)     ask the image model for it (again)
"""

import io
import logging
import os
from typing import Dict, Optional

from .format import SHOWS

logger = logging.getLogger(__name__)

STYLE = ("Two-colour risograph poster, burnt orange and near-black ink on warm off-white paper, "
         "bold flat shapes, visible grain and slight misregistration, generous empty space, "
         "the artwork fills the whole square frame edge to edge, no border, no margin, no paper edge, "
         "not a photograph of a print. No text, no letters, no logos.")

SUBJECTS: Dict[str, str] = {
    "station": "A radio mast on the roof of a small house at night, concentric rings of signal "
               "spreading out over a quiet street.",
    "cold_start": "A sunrise behind a kitchen table: a steaming mug, a laptop half open, the sun "
                  "as a large flat disc.",
    "main_thread": "A single thick thread running left to right across the page, passing through "
                   "the eye of a large needle, a small desk lamp beside it.",
    "the_diff": "Two overlapping speech bubbles, one orange and one black, the overlap a third "
                "shape; a plus and a minus cut out of them.",
    "show_and_tell": "A pair of open hands holding up a small hand-built gadget with a single "
                     "glowing lamp, tools laid out below.",
    "night_shift": "A lone lit window in a dark building under a large crescent moon, a desk "
                   "microphone in silhouette inside.",
    "garbage_collection": "An empty office at four in the morning: one desk, one bin overflowing "
                          "with crumpled paper, a small sweeping robot.",
}
SIZE = 1024


def art_dir() -> str:
    from . import radio_root

    d = os.path.join(radio_root(), "art")
    os.makedirs(d, exist_ok=True)
    return d


def keys() -> list:
    return ["station"] + [s.key for s in SHOWS]


def prompt(key: str) -> Optional[str]:
    subject = SUBJECTS.get(key)
    return f"{subject} {STYLE}" if subject else None


def path(key: str) -> Optional[str]:
    p = os.path.join(art_dir(), f"{os.path.basename(key)}.jpg")
    return p if os.path.exists(p) else None


def draw(key: str, seed: Optional[int] = None) -> Optional[str]:
    """Draw (or redraw) one cover. None if the image model is away."""
    text = prompt(key)
    if not text:
        return None
    try:
        import base64

        from PIL import Image

        from ..video.image_generator import ImageGenerationService

        made = ImageGenerationService().generate_image(text, height=SIZE, width=SIZE, seed=seed)
        raw = base64.b64decode(made["artifacts"][0]["base64"])
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        dst = os.path.join(art_dir(), f"{key}.jpg")
        tmp = dst + ".tmp"
        img.save(tmp, "JPEG", quality=88)
        os.replace(tmp, dst)
        return dst
    except Exception as e:
        logger.warning(f"radio art: could not draw {key}: {e}")
        return None


def draw_missing() -> Dict[str, bool]:
    return {k: bool(draw(k)) for k in keys() if not path(k)}
