"""The title card: the four seconds every episode opens on.

Replaces the static `media/hnfm_square.png`, which was one square picture
letterboxed into every format and credited tools the pipeline no longer
uses. The card is HTML: the HNFM lockup (five orange squares in a gradient
over the wordmark), "presented by brian", a one-line tagline for the episode,
and a credits strip naming the models that actually made it — read from the
audit trail and config, not typed in. It is laid out per aspect ratio and
rendered to a PNG by the Chromium sidecar (`/card`), so it is pixel-exact at
1280x720, 1024x1024 and 720x1280 rather than scaled.

Logos: each vendor gets a monogram tile drawn here. Drop an SVG at
`media/logos/<vendor>.svg` and it is used instead — the pipeline does not
ship third-party brand files.
"""

import base64
import hashlib
import html as _html
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

MEDIA_DIR = Path(__file__).parent / "media"
LOGO_DIR = MEDIA_DIR / "logos"

PRESENTER = os.getenv("HNFM_PRESENTER", "brian")

# The orange ramp over the wordmark, dark to bright, left to right.
SQUARES = ["#6f3410", "#8c4210", "#b5540c", "#d96208", "#ff6a00"]

# Who can appear in the credits. `accent` colours the monogram tile.
VENDORS = {
    "nvidia":     {"name": "NVIDIA",            "accent": "#76b900", "mono": "N"},
    "bfl":        {"name": "Black Forest Labs", "accent": "#ffffff", "mono": "B"},
    "nari":       {"name": "Nari Labs",         "accent": "#ff7ab6", "mono": "N"},
    "lightricks": {"name": "Lightricks",        "accent": "#b388ff", "mono": "L"},
    "hyperframes": {"name": "HyperFrames",      "accent": "#5eead4", "mono": "H"},
}

# Per-format geometry: the lockup width as a share of the frame, and how the
# strip at the bottom lays out. A portrait card stacks; a wide one spreads.
LAYOUT = {
    "16:9": {"lockup": 0.42, "tagline": 0.62, "credits_cols": 5, "pad": 0.045},
    "1:1":  {"lockup": 0.62, "tagline": 0.78, "credits_cols": 3, "pad": 0.05},
    "9:16": {"lockup": 0.78, "tagline": 0.86, "credits_cols": 2, "pad": 0.06},
}


# ---------------------------------------------------------------------------
# Credits: what made this episode
# ---------------------------------------------------------------------------


def credits_for(item_id: int = None, run: int = None, seg: int = None) -> List[dict]:
    """[{vendor, name, accent, products: [...]}] in strip order.

    Derived, not declared: the language and vision model from the steps the
    story actually ran, the image model from the configured backend, the
    voice from TTS_BACKEND, motion only if this segment has an LTX clip, and
    HyperFrames only if its media plan used one. With no story given (the
    preview page's sample), every vendor in the current stack appears.
    """
    products = {k: [] for k in VENDORS}

    llm_models = set()
    used_ltx = used_hyperframes = False
    if item_id is not None and run is not None:
        try:
            from ..db import steps as _steps

            for st in _steps.list_steps(item_id, run, seg):
                if st.get("status") in ("ok", "superseded") and st.get("model"):
                    llm_models.add(st["model"])
        except Exception as e:
            logger.debug(f"title card: steps unavailable ({e})")
        if seg is not None:
            try:
                from ..utils.segment_utils import (
                    get_segment, get_segment_image, list_segment_images,
                )

                for idx in list_segment_images(item_id, run, seg):
                    si = get_segment_image(item_id, run, seg, idx)
                    if si and getattr(si, "video_clip_path", None):
                        used_ltx = True
                        break
                segment = get_segment(item_id, run, seg)
                plan = (getattr(segment, "meta_plan", None) or []) if segment else []
                used_hyperframes = any(p.get("template") == "hyperframe" for p in plan)
            except Exception as e:
                logger.debug(f"title card: segment detail unavailable ({e})")
    sample = item_id is None

    if sample or any("nemotron" in m or "omni" in m for m in llm_models) or not llm_models:
        products["nvidia"].append("Nemotron 3")

    backend = os.getenv("IMAGE_GENERATION_BACKEND", "NIM").upper()
    products["bfl"].append("FLUX.1 Krea" if backend == "INVOKEAI" else "FLUX.2")

    tts = os.getenv("TTS_BACKEND", "magpie").lower()
    if tts == "dia":
        products["nari"].append("Dia")
    else:
        products["nvidia"].append("Magpie TTS")

    if sample or used_ltx:
        products["lightricks"].append("LTX-2")
    if sample or used_hyperframes:
        products["hyperframes"].append("kinetic text")

    out = []
    for key in ("nvidia", "bfl", "nari", "lightricks", "hyperframes"):
        if products[key]:
            out.append({"vendor": key, **VENDORS[key], "products": products[key]})
    return out


def tagline_for(item_id: int, run: int) -> str:
    """One line on what the episode is about, at no cost.

    The Story Brief's thesis first — it is written as a claim, which is what
    a tagline is. Then the run's short description, then the summary's first
    sentence. Whatever wins is stripped of "The article announces…" framing:
    the card is the episode speaking, not a review of the page.
    """
    candidates = []
    title = ""
    try:
        from ..db import repo as _repo

        item = _repo.get_item(item_id)
        title = " ".join(((item.title if item else "") or "").split()).lower()
        brief = ((_repo.get_latest_story_brief(item_id) or {}).get("brief") or {})
        candidates.append(brief.get("thesis") or "")
    except Exception:
        pass
    try:
        from ..utils.run_utils import get_run

        pr = get_run(item_id, run)
    except Exception:
        pr = None
    if pr:
        candidates.append(getattr(pr, "short_description", "") or "")
        candidates.append((pr.summary or "").strip())
    for text in candidates:
        text = _deframe(" ".join((text or "").split()))
        # A thesis that merely restates the headline adds nothing under a
        # card that is about to show the headline's video.
        if not text or text.lower().rstrip(".") == title.rstrip("."):
            continue
        if len(text) > TAGLINE_MAX:
            first = re.split(r"(?<=[.!?])\s", text)[0]
            text = first if len(first) <= TAGLINE_MAX else _clause(text, TAGLINE_MAX)
        return text.rstrip(".")
    return ""


TAGLINE_MAX = 100

_FRAMING = re.compile(
    r"^(?:the|this)\s+(?:article|post|piece|story|author|blog post|page)\s+"
    r"(?:announces|describes|discusses|explains|argues|reports|presents|introduces|"
    r"details|covers|explores|examines|shows|outlines)\s+(?:that\s+)?",
    re.I,
)


def _deframe(text: str) -> str:
    out = _FRAMING.sub("", text, count=1)
    return out[:1].upper() + out[1:] if out else out


def _clause(text: str, n: int) -> str:
    """Cut at the last clause boundary that fits, so the line ends whole.

    "…brain and central nervous system, containing over 166,000 neurons…"
    becomes "…brain and central nervous system" — a phrase, not a stump with
    an ellipsis. Falls back to a word cut only when no boundary fits.
    """
    head = text[:n + 1]
    best = -1
    for sep in (", ", "; ", " — ", ": ", " while ", " which ", " that "):
        i = head.rfind(sep)
        if i > n * 0.45 and i > best:
            best = i
    if best > 0:
        return text[:best].rstrip(",;:— ")
    return _clip(text, n)


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


# ---------------------------------------------------------------------------
# Markup
# ---------------------------------------------------------------------------

_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Archivo+Black&family=Archivo:wght@500;700"
    "&family=IBM+Plex+Mono:wght@500&family=Fraunces:opsz,wght@9..144,600&display=block"
)

# A "+" every 100px, in a dark orange that reads as texture, not content.
_PLUS_TILE = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'>"
    "<path d='M50 42v16M42 50h16' stroke='%23472208' stroke-width='2'/></svg>"
)


def _logo_html(v: dict) -> str:
    """The vendor's mark: a real SVG if one has been dropped in, else a tile."""
    path = LOGO_DIR / f"{v['vendor']}.svg"
    if path.exists():
        data = base64.b64encode(path.read_bytes()).decode()
        return f'<img class="mark" src="data:image/svg+xml;base64,{data}" alt="{_html.escape(v["name"])}">'
    return (
        f'<span class="mark tile" style="--accent:{v["accent"]}">'
        f'<span>{_html.escape(v["mono"])}</span></span>'
    )


def build_html(fmt: str, width: int, height: int, tagline: str = "",
               credits: Optional[List[dict]] = None,
               presenter: str = PRESENTER) -> str:
    """The card as a self-contained document sized exactly to the frame."""
    lay = LAYOUT.get(fmt, LAYOUT["16:9"])
    credits = credits if credits is not None else credits_for()
    lockup_w = int(width * lay["lockup"])
    # Archivo Black's HNFM spans about 2.62em at -0.03em tracking; the
    # wordmark is set by SVG textLength anyway, so this only sizes the box.
    sq_h = int(lockup_w * 0.185)
    wm_h = int(lockup_w * 0.30)
    pad = int(min(width, height) * lay["pad"])
    base = min(width, height)
    tag_size = int(base * (0.032 if fmt == "16:9" else 0.036))
    pill_size = int(base * 0.028)
    credit_size = int(base * 0.021)

    squares = "".join(
        f'<span style="background:{c}"></span>' for c in SQUARES
    )
    strip = "".join(
        f'<div class="credit">{_logo_html(v)}'
        f'<div class="who"><span class="vendor">{_html.escape(v["name"])}</span>'
        f'<span class="what">{_html.escape(" · ".join(v["products"]))}</span></div></div>'
        for v in credits
    )
    tag = (
        f'<p class="tagline">{_html.escape(tagline)}</p>' if tagline
        else '<p class="tagline muted">Hacker News, watchable.</p>'
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{_FONTS}" rel="stylesheet">
<style>
  html, body {{ margin: 0; width: {width}px; height: {height}px; overflow: hidden; }}
  body {{
    background: #000 url("{_PLUS_TILE}") center / 100px 100px;
    color: #fff; font-family: "Archivo", system-ui, sans-serif;
    display: grid; grid-template-rows: 1fr auto; box-sizing: border-box;
    padding: {pad}px;
  }}
  .hero {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: {int(base*0.035)}px; }}
  .lockup {{ width: {lockup_w}px; }}
  .squares {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 3px; height: {sq_h}px; }}
  .squares span {{ display: block; border: 1px solid #1a0d04; }}
  .wordmark {{ display: block; width: {lockup_w}px; height: {wm_h}px; margin-top: 4px; }}
  .wordmark text {{ font-family: "Archivo Black", "Archivo", sans-serif; font-weight: 900; fill: #fff; letter-spacing: -0.03em; }}
  .pill {{
    display: inline-flex; align-items: center; gap: {int(pill_size*0.9)}px;
    border: 1.5px solid #3a3a3a; border-radius: 999px; padding: {int(pill_size*0.35)}px {int(pill_size*0.35)}px {int(pill_size*0.35)}px {int(pill_size*1.1)}px;
    font-family: "IBM Plex Mono", monospace; font-size: {pill_size}px; letter-spacing: 0.02em; text-transform: uppercase;
  }}
  .pill b {{ font-family: "Fraunces", Georgia, serif; font-weight: 600; text-transform: none; letter-spacing: 0;
             background: #e9d829; color: #1a1a00; border-radius: 999px; padding: {int(pill_size*0.25)}px {int(pill_size*1.0)}px; font-size: {int(pill_size*1.25)}px; }}
  .tagline {{ margin: 0; max-width: {int(width * lay["tagline"])}px; text-align: center;
             font-size: {tag_size}px; line-height: 1.3; font-weight: 500; color: #eaeaea; text-wrap: balance; }}
  .tagline.muted {{ color: #9a9a9a; }}
  .credits {{ display: grid; grid-template-columns: repeat({min(lay["credits_cols"], max(1, len(credits)))}, max-content);
              justify-content: {"space-between" if len(credits) > 1 else "start"}; gap: {int(base*0.02)}px {int(base*0.03)}px;
              align-items: center; border-top: 1px solid #232323; padding-top: {int(base*0.028)}px; }}
  .credit {{ display: flex; align-items: center; gap: {int(credit_size*0.7)}px; min-width: 0; }}
  .mark {{ width: {int(credit_size*2.4)}px; height: {int(credit_size*2.4)}px; flex: none; object-fit: contain; }}
  .tile {{ display: inline-grid; place-items: center; border-radius: {int(credit_size*0.55)}px; background: #141414; border: 1px solid #2a2a2a; }}
  .tile span {{ font-family: "Archivo Black", sans-serif; color: var(--accent); font-size: {int(credit_size*1.3)}px; line-height: 1; }}
  .who {{ display: flex; flex-direction: column; min-width: 0; }}
  .vendor {{ font-weight: 700; font-size: {credit_size}px; letter-spacing: 0.01em; white-space: nowrap; }}
  .what {{ font-family: "IBM Plex Mono", monospace; font-size: {int(credit_size*0.82)}px; color: #9a9a9a; white-space: nowrap; }}
</style></head>
<body>
  <div class="hero">
    <div class="lockup">
      <div class="squares">{squares}</div>
      <svg class="wordmark" viewBox="0 0 1000 300" preserveAspectRatio="none" aria-label="HNFM">
        <text x="0" y="292" font-size="330" textLength="1000" lengthAdjust="spacingAndGlyphs">HNFM</text>
      </svg>
    </div>
    <div class="pill">Presented by <b>{_html.escape(presenter)}</b></div>
    {tag}
  </div>
  <div class="credits">{strip}</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_png(html: str, out_path: str, width: int, height: int) -> Optional[str]:
    """HTML -> PNG through the sidecar. None (and a log line) on failure."""
    import requests

    base = os.getenv("HYPERFRAMES_BASE_URL", "http://hyperframes:8088").rstrip("/")
    try:
        r = requests.post(
            f"{base}/card",
            json={"html": html, "output": out_path, "width": width, "height": height},
            timeout=int(os.getenv("HYPERFRAMES_TIMEOUT_SECONDS", "120")),
        )
        d = r.json() if r.content else {}
        if r.status_code == 200 and d.get("ok") and os.path.exists(out_path):
            return out_path
        logger.warning(f"title card render failed: {str(d)[:300] or r.status_code}")
    except Exception as e:
        logger.warning(f"title card render error (non-fatal): {e}")
    return None


def _fmt_key(fmt: str) -> str:
    return (fmt or "16:9").replace(":", "x")


def card_path_for(outputs_root: str, item_id: int, run: int, seg: int, fmt: str) -> str:
    return os.path.join(
        outputs_root, "hn", "item", str(item_id), "runs", str(run),
        "segments", str(seg), "title", f"title_{_fmt_key(fmt)}.png",
    )


def ensure_title_card(item_id: int, run: int, seg: int, fmt: str,
                      force: bool = False) -> Optional[str]:
    """The segment's title card PNG for its format, rendering it if needed.

    Called by the video step before the timeline is built. Non-fatal: if the
    sidecar is down the timeline falls back to the static card, and the
    episode still ships.
    """
    from ..content.art_direction import format_dims

    outputs_root = os.getenv("OUTPUTS_DIR", "/app/outputs")
    out = card_path_for(outputs_root, item_id, run, seg, fmt)
    if os.path.exists(out) and not force:
        return out
    w, h = format_dims(fmt)
    html = build_html(
        fmt, w, h, tagline=tagline_for(item_id, run),
        credits=credits_for(item_id, run, seg),
    )
    return render_png(html, out, w, h)


def preview_png(fmt: str, tagline: str = "", item_id: int = None, run: int = None,
                seg: int = None, force: bool = False) -> Optional[str]:
    """A rendered card for the preview page, cached by content."""
    from ..content.art_direction import format_dims

    w, h = format_dims(fmt)
    credits = credits_for(item_id, run, seg) if item_id else credits_for()
    if item_id and run and not tagline:
        tagline = tagline_for(item_id, run)
    html = build_html(fmt, w, h, tagline=tagline, credits=credits)
    key = hashlib.sha1(html.encode()).hexdigest()[:16]
    out = os.path.join(os.getenv("OUTPUTS_DIR", "/app/outputs"), "title-cards",
                       f"{_fmt_key(fmt)}-{key}.png")
    if os.path.exists(out) and not force:
        return out
    return render_png(html, out, w, h)
