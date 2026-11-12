"""One small, real request to every model and service the project leans on.

A health endpoint says a process is up. This asks each one to do its job
once: write a sentence, read a picture, say a line, hear it back, draw,
play, scrape, render, and (for the agent) answer. The result is kept so
the desk can show when each last worked and how long it took.

Nothing here is retried and nothing raises: a check that fails says why.
"""

import base64
import io
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SETTING = "inference.last_check"
LINE = "The quick brown fox files a bug report on Tuesday."


def _llm() -> str:
    from .content.llm_service import LLMService

    text = LLMService(task="radio.write").generate_content(
        "Reply with exactly one short sentence about the weather on Mars.")
    if not (text or "").strip():
        raise RuntimeError("the model returned nothing")
    return f"{os.getenv('LLM_MODEL', '')}: {text.strip()[:90]}"


def _vision() -> str:
    from PIL import Image
    from pydantic import BaseModel

    from .content.llm_service import LLMService

    class Seen(BaseModel):
        colour: str

    img = Image.new("RGB", (96, 96), (220, 30, 30))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    seen = LLMService(task="source_image.analyze").generate_structured_vision(
        "What single colour fills this image? One word.", Seen,
        image_b64=base64.b64encode(buf.getvalue()).decode())
    if "red" not in seen.colour.lower():
        raise RuntimeError(f"shown a red square, it said {seen.colour!r}")
    return f"{os.getenv('LLM_VISION_MODEL', '')}: saw {seen.colour}"


def _speech() -> Tuple[str, bytes]:
    from .radio import voice

    wav = voice.speak(LINE, "mia", fresh=True)
    if not wav or len(wav) < 5000:
        raise RuntimeError("no audio came back")
    return f"{len(wav) // 1024} KB of speech", wav


def _hearing(wav: Optional[bytes]) -> str:
    from .radio import qa

    if not wav:
        raise RuntimeError("nothing to listen to: speech failed")
    heard = qa.transcribe(wav)
    if heard is None:
        raise RuntimeError("the recogniser did not answer")
    match = qa.match(LINE, heard)
    if match < 0.8:
        raise RuntimeError(f"heard {heard!r} (match {match})")
    return f"heard {heard.strip()[:70]!r}, match {match}"


def _image() -> str:
    from PIL import Image

    from .video.image_generator import ImageGenerationService

    made = ImageGenerationService().generate_image(
        "a paper lantern on a desk, risograph print, two colours", height=512, width=512, seed=7)
    raw = base64.b64decode(made["artifacts"][0]["base64"])
    img = Image.open(io.BytesIO(raw))
    return f"{img.size[0]}x{img.size[1]}, {len(raw) // 1024} KB"


def _music() -> str:
    from .radio import music

    with tempfile.TemporaryDirectory() as d:
        out = music.make_bed("soft Rhodes piano, slow, 80 bpm, instrumental", 20, os.path.join(d, "bed.mp3"))
        if not out or not os.path.exists(out):
            raise RuntimeError("no music came back")
        return f"{os.path.getsize(out) // 1024} KB of music"


def _scrape() -> str:
    from .scraper.content_scraper import ContentScraper

    got = ContentScraper()._scrape_with_local_firecrawl("https://example.com")
    if not got.success or "Example Domain" not in (got.content or "") + (got.title or ""):
        raise RuntimeError(got.error or "the page came back without its text")
    return f"{len(got.content)} characters of example.com"


def _render() -> str:
    from .hyperframes.produce import produce_hyperframe_clip

    d = os.path.join(os.getenv("OUTPUTS_DIR", "/app/outputs"), "tmp", "inference_check")
    os.makedirs(d, exist_ok=True)
    out = produce_hyperframe_clip(d, "bigstat", {"stat": "1", "label": "render check"}, "default",
                                  640, 360, 1.0, fps=15, quality="draft")
    if not out:
        raise RuntimeError("the renderer made no clip")
    return f"{os.path.getsize(out) // 1024} KB clip"


def _motion() -> str:
    from .video import ltx_service

    if not ltx_service.is_available(force=True):
        raise RuntimeError("the video model is not running (it is kept stopped)")
    return "answering"


def _agent() -> str:
    from .hyperframes import hermes

    return hermes.ping()


# name, what it is for, the check, whether the project can work without it
CHECKS: List[Tuple[str, str, Callable, bool]] = [
    ("writer", "Every script, brief, score and digest", _llm, False),
    ("vision", "Reading the pictures found in articles", _vision, True),
    ("speech", "Every voice on the radio and in the videos", _speech, False),
    ("hearing", "Checking speech against its script, and timing captions", _hearing, False),
    ("image", "Covers, illustrations and video stills", _image, True),
    ("music", "Beds, stings and songs", _music, True),
    ("scrape", "Fetching the article behind a story", _scrape, False),
    ("render", "Turning HTML compositions into video", _render, True),
    ("agent", "Hermes, which writes the video compositions", _agent, True),
    ("motion", "Image-to-video clips (kept stopped)", _motion, True),
]


def check(names: Optional[List[str]] = None) -> Dict:
    """Run the checks in order and keep the result."""
    rows, wav = [], None
    for name, purpose, fn, optional in CHECKS:
        if names and name not in names:
            continue
        t = time.time()
        row = {"name": name, "purpose": purpose, "optional": optional}
        try:
            if name == "speech":
                detail, wav = fn()
            elif name == "hearing":
                if wav is None:
                    _d, wav = _speech()
                detail = fn(wav)
            else:
                detail = fn()
            row.update(ok=True, detail=detail)
        except Exception as e:
            row.update(ok=False, detail=str(e)[:240])
        row["seconds"] = round(time.time() - t, 1)
        rows.append(row)
        logger.info(f"inference check: {name} {'ok' if row['ok'] else 'FAILED'} in {row['seconds']}s: {row['detail']}")
    result = {"at": datetime.now(timezone.utc).isoformat(), "checks": rows,
              "ok": all(r["ok"] or r["optional"] for r in rows),
              "working": sum(1 for r in rows if r["ok"]), "of": len(rows)}
    if not names:
        try:
            from .db import repo

            repo.set_setting(SETTING, result)
        except Exception as e:
            logger.warning(f"inference check: could not keep the result: {e}")
    return result


def last() -> Optional[Dict]:
    from .db import repo

    return repo.get_setting(SETTING)
