"""Produce a finished HyperFrames clip for one section.

Thin glue: build the composition project, render it via the sidecar, return the
clip path. Kept separate from the meta-sequencer so the media-production step is
reusable and the whole HyperFrames layer stays swappable.
"""

import os
import logging

from .compositions import build_project
from .render_client import render_project

logger = logging.getLogger(__name__)


def produce_hyperframe_clip(
    out_dir: str, recipe: str, content: dict, theme_key: str,
    width: int, height: int, duration: float,
    bg_image: str = None, fmt: str = "mp4", fps: int = 30, quality: str = "standard",
) -> str:
    """Build + render a hyperframe clip; returns the output path or None."""
    proj = os.path.join(out_dir, "hf_project")
    build_project(recipe, content, theme_key, width, height, duration, proj, bg_image)
    out = os.path.join(out_dir, f"hyperframe.{fmt}")
    if render_project(proj, out, fmt=fmt, fps=fps, quality=quality):
        logger.info(f"🎬 hyperframe rendered ({recipe}, {duration:.1f}s): {out}")
        return out
    logger.warning(f"hyperframe render failed (recipe={recipe})")
    return None
