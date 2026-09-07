"""A photograph of the page a story links to.

The card for "K2 Horizon: A connected fleet of six open models" tells you its
score, its tags and its domain, and nothing at all about what is on the other
end of the link. A thumbnail is the cheapest way to know whether that is a
paper, a product page, a GitHub repo or a wall of text.

Captured with the chromium already running in the `hyperframes` sidecar rather
than a screenshot API: the browser is there, the outputs volume is mounted at
the same path in both containers, and a third-party service would mean handing
someone else the reading list. The sidecar refuses non-http(s) URLs and private
addresses — it is pointing a browser at strangers' URLs from inside the
network, so that guard lives next to the browser, not here.
"""

import json
import logging
import os
import time
import urllib.request

logger = logging.getLogger(__name__)

# Wide enough to read a headline at card size on a retina display, small enough
# that twenty of them on one page are not a download.
THUMB_W = 600
JPEG_QUALITY = 78

# What the browser is asked to render, before downscaling. A desktop viewport,
# because most pages lay out for one and a phone-width shot of a documentation
# site is a column of nothing.
SHOT_W, SHOT_H = 1200, 750

# Don't re-photograph a URL that just failed. Most failures are permanent —
# the domain is gone, it 403s a headless browser, it needs a login — and a
# card that retries on every render turns a dead link into a load of traffic.
MISS_TTL_SECONDS = 6 * 3600


def _base(item_id: int) -> str:
    root = os.getenv("OUTPUTS_ROOT", os.getenv("OUTPUTS_DIR", "/app/outputs"))
    return os.path.join(root, "hn", "item", str(item_id))


def thumb_path(item_id: int) -> str:
    return os.path.join(_base(item_id), "thumb.jpg")


def _miss_path(item_id: int) -> str:
    return os.path.join(_base(item_id), "thumb.miss")


def has_thumb(item_id: int) -> bool:
    p = thumb_path(item_id)
    return os.path.exists(p) and os.path.getsize(p) > 0


def recently_missed(item_id: int) -> bool:
    """True if a capture failed recently enough that retrying is pointless."""
    p = _miss_path(item_id)
    try:
        return (time.time() - os.path.getmtime(p)) < MISS_TTL_SECONDS
    except OSError:
        return False


def _note_miss(item_id: int, why: str) -> None:
    try:
        os.makedirs(_base(item_id), exist_ok=True)
        with open(_miss_path(item_id), "w") as f:
            f.write(why[:500])
    except OSError as e:
        logger.debug(f"could not record thumbnail miss for {item_id}: {e}")


def note_no_url(item_id: int) -> None:
    """A self-post has no external page and never will."""
    _note_miss(item_id, "no external url")


def _sidecar(url: str, out_png: str) -> dict:
    base = os.getenv("HYPERFRAMES_BASE_URL", "http://hyperframes:8088")
    body = json.dumps({
        "url": url, "output": out_png, "width": SHOT_W, "height": SHOT_H,
    }).encode()
    req = urllib.request.Request(
        f"{base}/shot", data=body,
        headers={"content-type": "application/json"},
    )
    # The sidecar spends up to 10s identifying the page and up to 25s
    # photographing it, so it must be allowed to exceed both before this side
    # gives up — otherwise a slow-but-fine page is recorded as a timeout here
    # and never retried.
    with urllib.request.urlopen(req, timeout=50) as r:
        return json.loads(r.read())


def capture(item_id: int, url: str, force: bool = False) -> str:
    """Photograph `url` and store a thumbnail for `item_id`. Path, or "".

    Never raises: a card without a picture is a card, and a card that failed to
    build is a broken page.
    """
    if not url:
        return ""
    if not force:
        if has_thumb(item_id):
            return thumb_path(item_id)
        if recently_missed(item_id):
            return ""

    out_png = os.path.join(_base(item_id), "thumb.png")
    t0 = time.time()
    try:
        res = _sidecar(url, out_png)
    except Exception as e:
        # A 500 from the sidecar carries its own reason in the body; urllib
        # raises on it, so the reason is worth reading out rather than logging
        # "HTTP Error 500".
        detail = ""
        body = getattr(e, "read", None)
        if body:
            try:
                detail = json.loads(body()).get("error") or ""
            except Exception:
                pass
        why = detail or str(e)
        logger.info(f"thumbnail failed for {item_id} ({url[:60]}): {why}")
        _note_miss(item_id, why)
        return ""

    if not res.get("ok") or not os.path.exists(out_png):
        why = res.get("error") or f"exit {res.get('code')}"
        logger.info(f"thumbnail failed for {item_id} ({url[:60]}): {why}")
        _note_miss(item_id, why)
        return ""

    try:
        from PIL import Image

        with Image.open(out_png) as im:
            im = im.convert("RGB")
            h = max(1, round(im.height * THUMB_W / im.width))
            im = im.resize((THUMB_W, h), Image.LANCZOS)
            im.save(thumb_path(item_id), "JPEG", quality=JPEG_QUALITY,
                    optimize=True)
    except Exception as e:
        logger.warning(f"thumbnail encode failed for {item_id}: {e}")
        _note_miss(item_id, str(e))
        return ""
    finally:
        try:
            os.remove(out_png)
        except OSError:
            pass

    try:
        os.remove(_miss_path(item_id))
    except OSError:
        pass

    kb = os.path.getsize(thumb_path(item_id)) // 1024
    logger.info(
        f"thumbnail for {item_id}: {kb}KB in {time.time() - t0:.1f}s "
        f"({url[:60]})"
    )
    return thumb_path(item_id)
