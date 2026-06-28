"""HyperFrames composition recipes for hn.fm.

Each recipe is a small, tasteful, *animated structured-text* layout — the kind of
thing HyperFrames is genuinely good at (beautiful kinetic typography), used as
short accent clips sprinkled through a video, NOT as full slideware. The agent
(meta-sequencer) picks a recipe and supplies the content; the design identity
(from the take's theme) drives colors + fonts so clips share a common language.

A recipe returns (body_html, gsap_js). `build_project` wraps it into a complete
self-contained HyperFrames project (index.html) ready for the render sidecar.

Recipes are intentionally modular: add/replace one without touching the rest, and
the whole layer can be swapped out later if HyperFrames isn't the long-term tool.
"""

import os
import re
import shutil
import html as _html

from .design_identity import identity_for, DesignIdentity

GSAP_CDN = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"


def _esc(s) -> str:
    return _html.escape(str(s or ""))


def _sizes(w: int, h: int) -> dict:
    """Type/spacing scale relative to canvas size (works for 16:9 / 1:1 / 9:16)."""
    return {
        "title": max(52, round(w * 0.075)),
        "kicker": max(15, round(w * 0.018)),
        "point": max(22, round(w * 0.032)),
        "stat": max(110, round(w * 0.20)),
        "quote": max(40, round(w * 0.055)),
        "pad": round(w * 0.085),
        "gap": round(h * 0.022),
    }


# ---- recipes: each returns (body_html, gsap_js) -----------------------------

def _recipe_keypoints(c: dict, d: DesignIdentity, s: dict) -> tuple:
    kicker = _esc(c.get("kicker") or "key points")
    title = _esc(c.get("title") or "")
    pts = [p for p in (c.get("points") or []) if p][:4]
    lis = "\n".join(
        f'<li class="pt"><span class="dot"></span><span>{_esc(p)}</span></li>' for p in pts
    )
    body = f"""
      <div class="kicker">{kicker}</div>
      <div class="rule"></div>
      <h1 class="title">{title}</h1>
      <ul class="points">{lis}</ul>"""
    gsap = """
      tl.from('.kicker', {opacity:0, y:18, duration:0.5}, 0.1);
      tl.from('.rule', {scaleX:0, transformOrigin:'left center', duration:0.5}, 0.2);
      tl.from('.title', {opacity:0, y:36, duration:0.7, ease:'power3.out'}, 0.3);
      tl.from('.pt', {opacity:0, x:-30, duration:0.5, stagger:0.18, ease:'power2.out'}, 0.7);
      tl.from('.dot', {scale:0, duration:0.4, stagger:0.18, ease:'back.out(2)'}, 0.75);"""
    return body, gsap


def _recipe_bigstat(c: dict, d: DesignIdentity, s: dict) -> tuple:
    stat = _esc(c.get("stat") or "")
    label = _esc(c.get("label") or "")
    sub = _esc(c.get("sub") or "")
    body = f"""
      <div class="stat-wrap">
        <div class="stat">{stat}</div>
        <div class="stat-label">{label}</div>
        {f'<div class="stat-sub">{sub}</div>' if sub else ''}
      </div>"""
    gsap = """
      tl.from('.stat', {opacity:0, scale:0.6, filter:'blur(14px)', duration:0.8, ease:'power4.out'}, 0.2);
      tl.from('.stat-label', {opacity:0, y:24, duration:0.6}, 0.7);
      tl.from('.stat-sub', {opacity:0, duration:0.6}, 0.95);"""
    return body, gsap


def _recipe_quote(c: dict, d: DesignIdentity, s: dict) -> tuple:
    quote = _esc(c.get("quote") or c.get("title") or "")
    attr = _esc(c.get("attribution") or "")
    body = f"""
      <div class="mark">&ldquo;</div>
      <blockquote class="quote">{quote}</blockquote>
      {f'<div class="attr">— {attr}</div>' if attr else ''}"""
    gsap = """
      tl.from('.mark', {opacity:0, scale:0.4, duration:0.6, ease:'back.out(2)'}, 0.1);
      tl.from('.quote', {opacity:0, y:30, duration:0.8, ease:'power3.out'}, 0.35);
      tl.from('.attr', {opacity:0, x:-20, duration:0.6}, 0.9);"""
    return body, gsap


def _recipe_compare(c: dict, d: DesignIdentity, s: dict) -> tuple:
    left = c.get("left") or {}
    right = c.get("right") or {}
    title = _esc(c.get("title") or "")

    def col(side, data):
        return f"""
        <div class="col {side}">
          <div class="col-label">{_esc(data.get('label'))}</div>
          <div class="col-body">{_esc(data.get('text'))}</div>
        </div>"""
    body = f"""
      {f'<h1 class="title compare-title">{title}</h1>' if title else ''}
      <div class="cols">
        {col('left', left)}
        <div class="vs">vs</div>
        {col('right', right)}
      </div>"""
    gsap = """
      tl.from('.compare-title', {opacity:0, y:20, duration:0.5}, 0.1);
      tl.from('.col.left', {opacity:0, x:-60, duration:0.7, ease:'power3.out'}, 0.3);
      tl.from('.col.right', {opacity:0, x:60, duration:0.7, ease:'power3.out'}, 0.3);
      tl.from('.vs', {opacity:0, scale:0, duration:0.5, ease:'back.out(2)'}, 0.7);"""
    return body, gsap


RECIPES = {
    "keypoints": _recipe_keypoints,
    "bigstat": _recipe_bigstat,
    "quote": _recipe_quote,
    "compare": _recipe_compare,
}


def _css(d: DesignIdentity, s: dict, w: int, h: int) -> str:
    return f"""
    *{{margin:0;padding:0;box-sizing:border-box}}
    html,body{{width:{w}px;height:{h}px;overflow:hidden;background:{d.bg};color:{d.fg};
      font-family:'{d.body_font}',system-ui,sans-serif;font-weight:{d.body_weight}}}
    #stage{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:{d.bg}}}
    .bg{{position:absolute;inset:0;background-size:cover;background-position:center;
      opacity:0.16;filter:saturate(1.15) contrast(1.05)}}
    .scrim{{position:absolute;inset:0;background:linear-gradient(180deg,
      {d.bg}cc 0%, {d.bg}77 45%, {d.bg}ee 100%)}}
    .scene{{position:relative;z-index:10;width:100%;height:100%;display:flex;
      flex-direction:column;justify-content:center;padding:{s['pad']}px;gap:{s['gap']}px}}
    .kicker{{font-weight:{max(500, d.body_weight)};text-transform:uppercase;
      letter-spacing:.30em;font-size:{s['kicker']}px;color:{d.accent}}}
    .rule{{height:5px;width:{round(w*0.10)}px;background:{d.accent};border-radius:3px}}
    .title{{font-family:'{d.display_font}',serif;font-weight:{d.display_weight};
      font-size:{s['title']}px;line-height:1.02;letter-spacing:-0.035em;color:{d.fg}}}
    .points{{list-style:none;display:flex;flex-direction:column;gap:{round(s['gap']*0.8)}px;
      margin-top:{round(s['gap']*0.5)}px}}
    .pt{{display:flex;align-items:center;gap:{round(w*0.018)}px;font-size:{s['point']}px;
      color:{d.fg};font-weight:{d.body_weight}}}
    .dot{{flex:none;width:{round(s['point']*0.42)}px;height:{round(s['point']*0.42)}px;
      border-radius:50%;background:{d.accent}}}
    .stat-wrap{{display:flex;flex-direction:column;align-items:center;justify-content:center;
      height:100%;text-align:center;gap:{s['gap']}px}}
    .stat{{font-family:'{d.display_font}',serif;font-weight:900;font-size:{s['stat']}px;
      line-height:0.9;letter-spacing:-0.04em;color:{d.accent}}}
    .stat-label{{font-size:{round(s['point']*1.1)}px;color:{d.fg};max-width:80%}}
    .stat-sub{{font-size:{s['kicker']}px;color:{d.muted};text-transform:uppercase;letter-spacing:.2em}}
    .mark{{font-family:'{d.display_font}',serif;font-size:{round(s['title']*1.6)}px;
      color:{d.accent};line-height:0.5;opacity:0.8}}
    .quote{{font-family:'{d.display_font}',serif;font-weight:{d.display_weight};
      font-size:{s['quote']}px;line-height:1.18;letter-spacing:-0.02em;color:{d.fg}}}
    .attr{{font-size:{s['kicker']}px;color:{d.muted};text-transform:uppercase;letter-spacing:.22em}}
    .cols{{display:flex;align-items:stretch;gap:{round(w*0.03)}px;flex:1}}
    .col{{flex:1;display:flex;flex-direction:column;gap:{round(s['gap']*0.6)}px;
      justify-content:center;border-top:5px solid {d.accent};padding-top:{round(s['gap'])}px}}
    .col-label{{font-weight:{d.display_weight};font-family:'{d.display_font}',serif;
      font-size:{round(s['point']*1.3)}px;color:{d.fg}}}
    .col-body{{font-size:{s['point']}px;color:{d.muted}}}
    .vs{{align-self:center;font-family:'{d.display_font}',serif;font-size:{round(s['point']*1.4)}px;
      color:{d.accent};font-weight:900}}
    .compare-title{{font-size:{round(s['title']*0.7)}px;margin-bottom:{s['gap']}px}}
    """


def build_html(recipe: str, content: dict, theme_key: str, width: int, height: int,
               duration: float, bg_image_rel: str = None) -> str:
    """Render a complete self-contained HyperFrames composition HTML string."""
    d = identity_for(theme_key)
    s = _sizes(width, height)
    fn = RECIPES.get(recipe, _recipe_keypoints)
    body, gsap = fn(content or {}, d, s)
    bg = ""
    if bg_image_rel:
        bg = f'<div class="bg" style="background-image:url(\'{bg_image_rel}\')"></div><div class="scrim"></div>'
    fonts = (
        f'<link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link href="https://fonts.googleapis.com/css2?{identity_for(theme_key).font_query()}'
        f'&display=swap" rel="stylesheet">'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<script src="{GSAP_CDN}"></script>
{fonts}
<style>{_css(d, s, width, height)}</style>
</head><body>
  <div id="stage" data-composition-id="main" data-start="0" data-duration="{duration}"
       data-width="{width}" data-height="{height}">
    {bg}
    <div class="scene">{body}</div>
  </div>
  <script>
    const tl = gsap.timeline();
    {gsap}
    window.__timelines = window.__timelines || {{}};
    window.__timelines["main"] = tl;
  </script>
</body></html>"""


def build_project(recipe: str, content: dict, theme_key: str, width: int, height: int,
                  duration: float, out_dir: str, bg_image_path: str = None) -> str:
    """Write a complete project dir (index.html + optional bg). Returns its path."""
    os.makedirs(out_dir, exist_ok=True)
    bg_rel = None
    if bg_image_path and os.path.exists(bg_image_path):
        ext = os.path.splitext(bg_image_path)[1] or ".png"
        bg_rel = f"bg{ext}"
        shutil.copy(bg_image_path, os.path.join(out_dir, bg_rel))
    html = build_html(recipe, content, theme_key, width, height, duration, bg_rel)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)
    return out_dir
