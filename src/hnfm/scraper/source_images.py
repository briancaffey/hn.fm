"""Source images: the pictures on the page a story links to (plans/18).

Real images from the source are often better at telling the story than
anything we generate — the chart the post is about, the board someone built,
the screenshot of the bug. This module finds them, keeps them at a sane size,
and hands each one to the vision model for a verdict on whether and how a
video could use it.

    collect   HTML -> candidate {url, alt, origin}, chrome and junk removed
    store     download each, record what the page served, downscale, save
    analyze   one vision call per stored image (content/source_image_analysis)

Everything here is non-fatal per image: one 404 or one corrupt JPEG drops
that image, not the collection.
"""

import hashlib
import io
import logging
import os
import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# What we keep. Anything larger on its long edge is downscaled; the stored
# copy is what the vision model and the video renderer see.
MAX_DIM = int(os.getenv("SOURCE_IMAGES_MAX_DIM", "1536"))
# Refuse downloads past this: a 40 MB TIFF is not a source image, it is a
# mistake, and it would take a minute on the ingest lane.
MAX_DOWNLOAD_BYTES = int(os.getenv("SOURCE_IMAGES_MAX_BYTES", str(15 * 1024 * 1024)))
# Below this on the short edge it is an icon, a thumbnail, or a tracking pixel.
MIN_EDGE = 240
# How many candidates to download at all, and how many stored images to
# analyse. Downloading is cheap; a vision call is a few seconds each.
MAX_CANDIDATES = int(os.getenv("SOURCE_IMAGES_MAX_CANDIDATES", "12"))
ANALYZE_N = int(os.getenv("SOURCE_IMAGES_TOP_N", "6"))

_UA = "hn.fm/0.1 (+https://github.com/briancaffey/hn.fm)"

# Chrome, decoration and tracking, by URL hint. Broad on purpose: a real
# content image that happens to say "badge" in its path is a smaller loss
# than a hundred sponsor logos in the catalogue.
_JUNK = re.compile(
    r"(sprite|logo|icon|avatar|pixel|tracking|1x1|spacer|badge|emoji|favicon|"
    r"placeholder|loading|blank|gravatar|/ads?/|advert|banner|button|"
    r"share|social|twitter|facebook|linkedin|rss|feed|counter|beacon|"
    r"/wp-content/plugins/|widget|sponsor)",
    re.I,
)
_SKIP_EXT = {".svg", ".gif", ".ico", ".bmp", ".webm", ".mp4"}

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
_META_TAG = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")


def _attrs(tag: str) -> dict:
    out = {}
    for m in _ATTR.finditer(tag):
        out[m.group(1).lower()] = m.group(2) or m.group(3) or m.group(4) or ""
    return out


def _largest_srcset(srcset: str) -> Optional[str]:
    """The widest candidate in a srcset, or None if unparseable."""
    best, best_w = None, -1
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        url = bits[0]
        w = 0
        if len(bits) > 1:
            m = re.match(r"(\d+(?:\.\d+)?)([wx])", bits[1])
            if m:
                w = float(m.group(1)) * (1000 if m.group(2) == "x" else 1)
        if w > best_w:
            best, best_w = url, w
    return best


def _acceptable(url: str, trusted: bool = False) -> bool:
    """`trusted` skips the URL-hint filter: an og:image is the author's own
    choice of picture, and its path very often says "social" or "card"."""
    if not url or url.startswith("data:"):
        return False
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    if ext in _SKIP_EXT:
        return False
    return trusted or not _JUNK.search(url)


def collect(html: str, base_url: str) -> List[dict]:
    """Candidate images from the page, in page order, og:image first.

    `<img>` with a `srcset` contributes its widest candidate, and lazy-loaded
    images (`data-src`) are honoured — the v0 read only `src`, which on most
    modern blogs is a 1x1 placeholder. Same picture referenced twice is kept
    once; the same picture at two URLs is caught later by content hash.
    """
    out, seen = [], set()

    def add(url: str, alt: str, origin: str):
        url = urljoin(base_url, (url or "").strip())
        if url in seen or not _acceptable(url, trusted=(origin == "og:image")):
            return
        seen.add(url)
        out.append({"url": url, "alt": (alt or "").strip()[:300], "origin": origin})

    # Social cards first: the author chose this one picture to stand for the
    # page, which is exactly the judgement we want.
    for tag in _META_TAG.findall(html or ""):
        a = _attrs(tag)
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:secure_url", "twitter:image",
                   "twitter:image:src") and a.get("content"):
            add(a["content"], "", "og:image")

    for tag in _IMG_TAG.findall(html or ""):
        a = _attrs(tag)
        alt = a.get("alt", "")
        # Explicit tiny dimensions are page furniture whatever the URL says.
        try:
            if a.get("width") and int(re.sub(r"\D", "", a["width"]) or 0) < 64:
                continue
        except ValueError:
            pass
        srcset = a.get("srcset") or a.get("data-srcset")
        if srcset:
            best = _largest_srcset(srcset)
            if best:
                add(best, alt, "srcset")
                continue
        src = a.get("data-src") or a.get("data-lazy-src") or a.get("src")
        if src:
            add(src, alt, "img")
    return out


def fetch_html(url: str, timeout: int = 60) -> str:
    """The page's HTML, from firecrawl when it is up, else a plain GET.

    Firecrawl renders JavaScript and strips boilerplate, so its `html` is the
    better source. But a source-image pass must not depend on it being up:
    the plain page still has `<img>` tags, and a blog without JS-injected
    images loses nothing.
    """
    base = os.getenv("FIRECRAWL_BASE_URL", "http://localhost:3002")
    try:
        r = requests.post(
            f"{base}/v1/scrape",
            json={"url": url, "formats": ["html"], "onlyMainContent": False},
            timeout=timeout,
        )
        if r.status_code == 200:
            html = ((r.json().get("data") or {}).get("html")) or ""
            if html.strip():
                return html
        logger.info(f"source images: firecrawl gave no html for {url} ({r.status_code})")
    except Exception as e:
        logger.info(f"source images: firecrawl unavailable ({e}); fetching directly")
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": _UA})
        if r.status_code == 200 and "html" in (r.headers.get("content-type") or ""):
            return r.text
    except Exception as e:
        logger.warning(f"source images: direct fetch failed for {url}: {e}")
    return ""


def _download(url: str) -> Tuple[Optional[bytes], str]:
    """(bytes, content_type) or (None, reason)."""
    try:
        with requests.get(url, timeout=30, stream=True,
                          headers={"User-Agent": _UA, "Accept": "image/*,*/*;q=0.5"}) as r:
            if r.status_code != 200:
                return None, f"http {r.status_code}"
            ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
            declared = int(r.headers.get("content-length") or 0)
            if declared > MAX_DOWNLOAD_BYTES:
                return None, f"too large ({declared} bytes)"
            buf = io.BytesIO()
            for chunk in r.iter_content(65536):
                buf.write(chunk)
                if buf.tell() > MAX_DOWNLOAD_BYTES:
                    return None, f"too large (>{MAX_DOWNLOAD_BYTES} bytes)"
            return buf.getvalue(), ctype
    except Exception as e:
        return None, str(e)[:120]


def store(candidates: List[dict], out_dir: str, max_dim: int = None,
          limit: int = None) -> List[dict]:
    """Download, measure, downscale, save. Returns one dict per kept image.

    The record keeps both sizes — what the page served and what we saved —
    because the downscale is the point: nothing downstream should ever be
    handed a 6 MB photograph, and the catalogue should show that it was not.
    """
    max_dim = max_dim or MAX_DIM
    limit = limit or MAX_CANDIDATES
    os.makedirs(out_dir, exist_ok=True)
    kept, hashes = [], set()
    for cand in candidates:
        if len(kept) >= limit:
            break
        raw, ctype = _download(cand["url"])
        if raw is None:
            logger.info(f"source images: skip {cand['url'][:80]} — {ctype}")
            continue
        if len(raw) < 1500:
            continue
        sha1 = hashlib.sha1(raw).hexdigest()
        if sha1 in hashes:
            continue
        try:
            img = Image.open(io.BytesIO(raw))
            img.load()
        except Exception as e:
            logger.info(f"source images: undecodable {cand['url'][:80]} ({e})")
            continue
        if getattr(img, "is_animated", False):
            continue
        w, h = img.size
        if min(w, h) < MIN_EDGE:
            continue
        hashes.add(sha1)

        rgb = img.convert("RGB")
        resized = max(w, h) > max_dim
        if resized:
            rgb.thumbnail((max_dim, max_dim), Image.LANCZOS)
        index = len(kept) + 1
        path = os.path.join(out_dir, f"src_{index}.jpg")
        rgb.save(path, "JPEG", quality=88, optimize=True)
        kept.append({
            "index": index,
            "url": cand["url"], "alt": cand.get("alt") or "",
            "origin": cand.get("origin") or "img",
            "sha1": sha1, "content_type": ctype or None,
            "width": w, "height": h, "bytes": len(raw),
            "stored_width": rgb.size[0], "stored_height": rgb.size[1],
            "stored_bytes": os.path.getsize(path),
            "resized": resized, "path": path,
        })
        logger.info(
            f"📸 source image {index}: {w}x{h} {len(raw) // 1024} KB"
            + (f" -> {rgb.size[0]}x{rgb.size[1]} {os.path.getsize(path) // 1024} KB"
               if resized else "")
        )
    return kept


def ingest(url: str, out_dir: str, limit: int = None) -> List[dict]:
    """Page -> stored images (not yet analysed)."""
    html = fetch_html(url)
    if not html:
        return []
    candidates = collect(html, url)
    logger.info(f"📸 {len(candidates)} candidate source images on {url}")
    return store(candidates, out_dir, limit=limit) if candidates else []
