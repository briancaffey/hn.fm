"""Source images from the scraped article → ranked, described, stored.

Real images from the source material are often far better at telling the story
than anything we generate. This module pulls <img> tags from firecrawl's HTML,
ranks the top few by alt-text relevance (LLM), downloads + downscales them (so we
never ship huge images to the vision model), describes each with nemotron vision,
and stores metadata + description. These become high-quality real inputs the
agent can later use (style transfer, sequencing, image-to-video) alongside the
generated images.
"""

import os
import re
import io
import base64
import logging
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# Skip obvious chrome/decoration/tracking images by URL hint.
_JUNK = re.compile(
    r"(sprite|logo|icon|avatar|pixel|tracking|1x1|spacer|badge|emoji|favicon|"
    r"placeholder|loading|blank)",
    re.I,
)
_IMG_TAG = re.compile(r"<img[^>]+>", re.I)


def extract_images(html: str, base_url: str) -> list:
    """Parse <img src/alt> from HTML, resolve URLs, drop junk + dupes."""
    out, seen = [], set()
    for tag in _IMG_TAG.findall(html or ""):
        m = re.search(r'src=["\']([^"\']+)["\']', tag)
        if not m:
            continue
        u = m.group(1).strip()
        if u.startswith("data:"):
            continue
        u = urljoin(base_url, u)
        if u in seen or _JUNK.search(u):
            continue
        ext = os.path.splitext(urlparse(u).path)[1].lower()
        if ext in (".svg", ".gif", ".ico"):
            continue
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', tag)
        seen.add(u)
        out.append({"url": u, "alt": (alt_m.group(1).strip() if alt_m else "")})
    return out


def rank_images(images: list, summary: str, top_n: int = 4) -> list:
    """LLM picks the most interesting/relevant images by their alt text."""
    if len(images) <= top_n:
        return images
    from ..content.llm_service import LLMService

    listing = "\n".join(
        f"{i}: {im['alt'] or '(no alt text)'}" for i, im in enumerate(images)
    )
    prompt = (
        f"Article summary:\n{summary[:800]}\n\n"
        f"Candidate images (index: alt text):\n{listing}\n\n"
        f"Pick the {top_n} MOST interesting and relevant images for telling this "
        f"story visually. Prefer concrete, content-rich images over generic or "
        f"decorative ones. Respond with ONLY a JSON array of indices like [0,3,5]."
    )
    try:
        resp = LLMService().generate_content(prompt) or ""
        idxs = __import__("json").loads(re.search(r"\[[^\]]*\]", resp).group(0))
        picked = [images[i] for i in idxs if isinstance(i, int) and 0 <= i < len(images)]
        if picked:
            return picked[:top_n]
    except Exception as e:
        logger.warning(f"rank_images fell back to first {top_n}: {e}")
    return images[:top_n]


def _vision_describe(img_path: str) -> str:
    """Describe an image with nemotron vision via the LiteLLM gateway."""
    base = os.getenv("LLM_BASE_URL")
    if not base:
        return ""
    if not base.endswith("/v1"):
        base = base.rstrip("/") + "/v1"
    try:
        import openai

        client = openai.OpenAI(base_url=base, api_key=os.getenv("OPENAI_API_KEY") or "x")
        b64 = base64.b64encode(open(img_path, "rb").read()).decode()
        r = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "nemotron-omni"),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in 1-2 sentences: "
                     "what it shows, key subjects, and mood. Be concrete and factual."},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
            max_tokens=160,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        msg = r.choices[0].message
        return (msg.content or getattr(msg, "reasoning_content", "") or "").strip()
    except Exception as e:
        logger.warning(f"vision describe failed (non-fatal): {e}")
        return ""


def download_and_describe(images: list, out_dir: str, max_dim: int = 1024) -> list:
    """Download, downscale, and describe the chosen images."""
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for i, im in enumerate(images):
        try:
            r = requests.get(
                im["url"], timeout=30, headers={"User-Agent": "hn.fm/0.1 (briancaffey)"}
            )
            if r.status_code != 200 or len(r.content) < 2000:
                continue
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if min(img.size) < 200:  # skip tiny/thumbnail/icon
                continue
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim))
            path = os.path.join(out_dir, f"src_{i + 1}.jpg")
            img.save(path, "JPEG", quality=88)
            desc = _vision_describe(path)
            results.append({
                "url": im["url"], "alt": im["alt"], "local_path": path,
                "width": img.size[0], "height": img.size[1], "description": desc,
            })
            logger.info(f"📸 source image {i + 1}: '{im['alt'][:40]}' -> {desc[:70]}")
        except Exception as e:
            logger.warning(f"source image {i + 1} skipped: {e}")
    return results


def ingest(url: str, summary: str, out_dir: str, top_n: int = 4) -> list:
    """Full pass: scrape HTML → extract → rank → download+describe."""
    base = os.getenv("FIRECRAWL_BASE_URL", "http://localhost:3002")
    try:
        r = requests.post(
            f"{base}/v1/scrape",
            json={"url": url, "formats": ["html"], "onlyMainContent": True},
            timeout=60,
        )
        html = (r.json().get("data", {}) or {}).get("html", "") if r.status_code == 200 else ""
    except Exception as e:
        logger.warning(f"source-image scrape failed (non-fatal): {e}")
        return []
    images = extract_images(html, url)
    logger.info(f"📸 {len(images)} candidate source images for {url}")
    if not images:
        return []
    return download_and_describe(rank_images(images, summary, top_n), out_dir)
