"""Putting the article's own pictures into the video (plans/18).

Two halves. `cast` is one text call that matches analysed source images to
the narration sections they belong with — the chart while the result is
read out, the device while it is described — and says whether each should
appear untouched or be re-rendered in the take's art style. `place` and
`restyle_prompt` are what the image builder then does with a cast entry.

Deterministic guardrails sit between the model and the pipeline: only
usable images past an interest floor, each image once, at most a few
sections per take. The model chooses; the code enforces.
"""

import logging
import os
from typing import Dict, List, Optional

from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

TASK = "source_image.cast"

# How many sections of one take may show a real image. Past this the video
# stops being in its art style and starts being a slideshow of the article.
MAX_USES = int(os.getenv("SOURCE_IMAGES_MAX_USES", "3"))
# Below this the vision model did not think much of it, and neither should
# the director.
MIN_INTEREST = int(os.getenv("SOURCE_IMAGES_MIN_INTEREST", "55"))
# Never on screen as-is whatever the model says: they are not about the story.
_NEVER = {"logo"}


def eligible(images: List[dict]) -> List[dict]:
    return [
        im for im in images
        if im.get("usable") and (im.get("interest") or 0) >= MIN_INTEREST
        and im.get("kind") not in _NEVER and im.get("path")
        and os.path.exists(im["path"])
    ]


def _listing(images: List[dict]) -> str:
    return "\n".join(
        f"- id {im['id']}: [{im.get('kind')}] interest {im.get('interest')} — "
        f"{im.get('description')}"
        + (f" Text: \"{im['text_in_image'][:80]}\"" if im.get("text_in_image") else "")
        + (f" How: {im['use_hint']}" if im.get("use_hint") else "")
        for im in images
    )


def cast(sections: List[str], images: List[dict], theme_name: str,
         max_uses: int = None) -> Dict[int, dict]:
    """{section_index: {"image": <row>, "treatment": "as_is"|"restyle", "why"}}.

    Empty when there is nothing eligible, when the model casts nothing, or
    when the call fails — a take with no real images is the ordinary case,
    not an error.
    """
    from .llm_schemas import SourceImageCast
    from .llm_service import LLMService
    from .prompts import render

    max_uses = max_uses if max_uses is not None else MAX_USES
    pool = eligible(images)
    if not pool or not sections or max_uses <= 0:
        return {}
    by_id = {int(im["id"]): im for im in pool}

    try:
        prompt = render(
            TASK, theme_name=theme_name or "the take's style",
            sections="\n".join(f"{i}: {s[:220]}" for i, s in enumerate(sections, 1)),
            images=_listing(pool), max_uses=max_uses,
        )
        result = LLMService(task=TASK).generate_structured(prompt, SourceImageCast)
    except Exception as e:
        logger.warning(f"source image cast failed (non-fatal): {e}")
        return {}

    out: Dict[int, dict] = {}
    used = set()
    for entry in result.cast:
        if len(out) >= max_uses:
            break
        if not 1 <= entry.section <= len(sections) or entry.section in out:
            continue
        im = by_id.get(int(entry.image_id))
        if im is None or im["id"] in used:
            continue
        treatment = entry.treatment
        # Exact-content kinds are wasted on a restyle: a re-rendered chart is
        # a picture of a chart with different numbers.
        if im.get("kind") in ("chart", "screenshot", "code", "diagram", "map"):
            treatment = "as_is"
        used.add(im["id"])
        out[entry.section] = {"image": im, "treatment": treatment, "why": entry.why}
    logger.info(
        "🎞️  source images cast: "
        + (", ".join(f"§{k} <- #{v['image']['id']} {v['treatment']}"
                     for k, v in sorted(out.items())) or "none")
    )
    return out


def place(source_path: str, out_path: str, width: int, height: int) -> str:
    """Fit a real image into the take's frame without cropping it.

    Contain, not cover: a chart with its axis cut off is worse than a chart
    with margins. The margins are the image itself, blown up and blurred, so
    the frame reads as one picture rather than a picture on black.
    """
    img = Image.open(source_path).convert("RGB")
    scale = min(width / img.width, height / img.height)
    fg = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                    Image.LANCZOS)
    # The backdrop covers the frame; the blur hides that it is a stretch.
    cover = max(width / img.width, height / img.height)
    bg = img.resize((max(1, round(img.width * cover)), max(1, round(img.height * cover))),
                    Image.BILINEAR)
    bg = bg.crop(((bg.width - width) // 2, (bg.height - height) // 2,
                  (bg.width - width) // 2 + width, (bg.height - height) // 2 + height))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=max(8, width // 60)))
    bg = Image.eval(bg, lambda v: int(v * 0.55))
    bg.paste(fg, ((width - fg.width) // 2, (height - fg.height) // 2))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    bg.save(out_path, "PNG")
    return out_path


def restyle_prompt(image: dict, theme) -> str:
    """The edit instruction for flux: same picture, the take's look."""
    style = getattr(theme, "style", "") or ""
    name = getattr(theme, "name", "") or "the video's art style"
    subject = (image.get("description") or image.get("alt") or "the image").strip()
    return (
        f"Re-render this image as {name}: {style}. "
        f"Keep the subject, composition and framing exactly as they are — {subject}. "
        f"Change only the rendering style. High quality, coherent."
    )


def restyle(image: dict, theme, out_dir: str, filename: str, width: int,
            height: int, seed: Optional[int] = None) -> Optional[str]:
    """flux `/v1/images/edits` on the stored copy. Returns the path or None."""
    from ..image.image_service_factory import ImageServiceFactory

    svc = ImageServiceFactory.create_image_service()
    if not hasattr(svc, "generate_and_save_edit"):
        logger.info("source image restyle: backend has no edit endpoint")
        return None
    prompt = restyle_prompt(image, theme)
    # The edit endpoint wants the reference at the output size; `place`
    # gives it the framing the root frame will have anyway.
    ref = os.path.join(out_dir, "_source_ref.png")
    place(image["path"], ref, width, height)
    svc.generate_and_save_edit(prompt, ref, out_dir, filename, width=width,
                               height=height, seed=seed)
    try:
        os.remove(ref)
    except OSError:
        pass
    out = os.path.join(out_dir, filename)
    return out if os.path.exists(out) else None
