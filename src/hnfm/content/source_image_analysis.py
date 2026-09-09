"""What the vision model makes of a source image (plans/18).

One structured call per picture, through `LLMService` so the prompt is
versioned, the model comes from the `source_image.analyze` profile (an omni
route — a text route fail-closes on image payloads), and the tokens land on
the current pipeline step. The tokens are also returned per image, because
"what did it cost to look at this one" is a question the catalogue answers.
"""

import base64
import io
import logging
import time
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

TASK = "source_image.analyze"

# What the model is shown. Smaller than storage: the description does not
# improve past this and the prompt tokens scale with the pixels.
VISION_DIM = 768


def image_b64_for_vision(path: str, dim: int = VISION_DIM) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((dim, dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def analyze(path: str, *, title: str, summary: str, alt: str = "",
            origin: str = "") -> dict:
    """The analysis as a flat dict of row fields, or an `analysis_error`.

    Never raises: an image the model cannot look at is still a stored image
    with a size and a URL, and the catalogue should say the analysis failed
    rather than lose the row.
    """
    from .llm_schemas import SourceImageAnalysis
    from .llm_service import LLMService
    from .prompts import render

    svc = LLMService(task=TASK)
    t0 = time.time()
    try:
        prompt = render(
            TASK, title=title or "", summary=(summary or "")[:700],
            alt=alt or "(none)", origin=origin or "img",
        )
        result = svc.generate_structured_vision(
            prompt, SourceImageAnalysis, image_b64=image_b64_for_vision(path),
        )
    except Exception as e:
        logger.warning(f"source image analysis failed for {path}: {e}")
        return {
            "analysis_error": str(e)[:500],
            "analysis_model": svc.usage.get("model"),
            "tokens_in": svc.usage["tokens_in"] or None,
            "tokens_out": svc.usage["tokens_out"] or None,
            "analysis_seconds": round(time.time() - t0, 2),
        }
    return {
        "description": result.description.strip(),
        "kind": result.kind,
        "subjects": [s.strip() for s in result.subjects if s.strip()][:6],
        "text_in_image": result.text_in_image.strip()[:1000],
        "interest": int(result.interest),
        "usable": bool(result.usable),
        "use_hint": result.use_hint.strip(),
        "caveat": result.caveat.strip(),
        "analysis_model": svc.usage.get("model"),
        "tokens_in": svc.usage["tokens_in"],
        "tokens_out": svc.usage["tokens_out"],
        "analysis_seconds": round(time.time() - t0, 2),
        "analysis_error": None,
    }
