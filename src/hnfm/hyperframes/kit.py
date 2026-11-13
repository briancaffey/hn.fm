"""The story video's frame: everything about the composition that is not
a scene's own content.

The video is one HyperFrames project. `index.html` is the host: the
canvas, the palette as CSS variables, the narration, the captions, the
progress line and one slot per scene. Each scene is its own file under
`compositions/`, mounted into its slot for exactly as long as its part of
the narration lasts.

Code writes the host, the title card, the sign-off and a plain version of
every scene, so there is always a complete video. The author (Hermes)
replaces scene files one at a time; a scene that does not pass the checks
keeps its plain version.
"""

import html
import json
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional

from .design_identity import DesignIdentity, identity_for

GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
WIDTH, HEIGHT, FPS = 1280, 720, 24
# The bottom of the frame belongs to the captions: scenes keep out of it.
CAPTION_BAND = 150
SAFE = {"left": 80, "top": 64, "width": WIDTH - 160, "height": HEIGHT - CAPTION_BAND - 64}

_NUMBER = re.compile(
    r"(?<![\w.])(\$?\d[\d,]*(?:\.\d+)?\s?(?:%|GB|TB|MB|KB|ms|x|K|M|B|billion|million|trillion|percent|"
    r"tokens|hours|minutes|seconds|years|days)?)(?![\w])", re.I)


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def scene_id(n: int) -> str:
    return f"scene-{n:02d}"


def scene_file(n: int) -> str:
    return f"compositions/{scene_id(n)}.html"


def palette(theme: str) -> Dict:
    d = identity_for(theme)
    return {"bg": d.bg, "ink": d.fg, "muted": d.muted, "accent": d.accent,
            "display": d.display_font, "body": d.body_font,
            "display_weight": d.display_weight, "body_weight": d.body_weight,
            "dark": _is_dark(d.bg)}


def _is_dark(hex_colour: str) -> bool:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


def _fonts(d: DesignIdentity) -> str:
    fams = []
    for fam in dict.fromkeys((d.display_font, d.body_font)):
        fams.append(f"family={fam.replace(' ', '+')}:wght@300;400;600;800")
    return ('<link rel="preconnect" href="https://fonts.googleapis.com">'
            f'<link href="https://fonts.googleapis.com/css2?{"&".join(fams)}&display=swap" rel="stylesheet">')


def _css(d: DesignIdentity) -> str:
    """The shared look. Scenes use these variables and classes; anything a
    scene adds of its own is scoped to its own id."""
    dark = _is_dark(d.bg)
    veil = "rgba(0,0,0,.62)" if dark else "rgba(255,255,255,.82)"
    # A panel sits on the plain background; a veil sits on a picture.
    panel = "rgba(255,255,255,.08)" if dark else "rgba(0,0,0,.05)"
    return f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{d.bg};color:{d.fg};font-family:'{d.body_font}',system-ui,sans-serif;
  font-weight:{d.body_weight};-webkit-font-smoothing:antialiased}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;
  --bg:{d.bg};--ink:{d.fg};--muted:{d.muted};--accent:{d.accent};--veil:{veil};--panel:{panel};
  --display:'{d.display_font}',serif;--body:'{d.body_font}',system-ui,sans-serif}}
#k-bg{{position:absolute;inset:0;background:{d.bg}}}
.k-scene{{position:absolute;inset:0;overflow:hidden;color:var(--ink)}}
.k-safe{{position:absolute;left:{SAFE['left']}px;top:{SAFE['top']}px;width:{SAFE['width']}px;
  height:{SAFE['height']}px;display:flex;flex-direction:column;justify-content:center;gap:22px}}
.k-kicker{{font-family:var(--body);font-weight:600;font-size:22px;letter-spacing:.24em;
  text-transform:uppercase;color:var(--accent);margin:0}}
.k-title{{font-family:var(--display);font-weight:{d.display_weight};font-size:76px;line-height:1.02;
  letter-spacing:-.03em;margin:0;color:var(--ink)}}
.k-body{{font-family:var(--body);font-size:32px;line-height:1.3;margin:0;color:var(--ink)}}
.k-muted{{color:var(--muted)}}
.k-stat{{font-family:var(--display);font-weight:800;font-size:200px;line-height:.9;
  letter-spacing:-.04em;color:var(--accent);margin:0}}
.k-rule{{width:120px;height:6px;border-radius:3px;background:var(--accent)}}
.k-chip{{display:inline-block;padding:8px 18px;border-radius:999px;border:2px solid var(--accent);
  color:var(--accent);font-family:var(--body);font-weight:600;font-size:20px;letter-spacing:.12em;
  text-transform:uppercase}}
.k-card{{background:var(--veil);border-radius:18px;padding:28px 32px}}
.k-img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.k-shade{{position:absolute;inset:0;background:linear-gradient(180deg,transparent 30%,{d.bg} 100%)}}
.k-cap{{position:absolute;left:0;right:0;bottom:44px;display:flex;justify-content:center;z-index:40}}
.k-cap span{{max-width:1000px;padding:10px 24px;border-radius:12px;background:var(--veil);
  font-family:var(--body);font-weight:600;font-size:34px;line-height:1.25;text-align:center;color:var(--ink)}}
#k-chrome{{position:absolute;inset:0;z-index:50;pointer-events:none}}
#k-bug{{position:absolute;right:28px;top:24px;padding:6px 12px 6px 16px;border-radius:8px;background:var(--veil);
  font-family:var(--body);font-weight:800;font-size:18px;letter-spacing:.3em;color:var(--ink)}}
#k-track{{position:absolute;left:0;right:0;bottom:0;height:8px;background:var(--veil)}}
#k-bar{{width:100%;height:100%;background:var(--accent);transform-origin:0 50%}}
"""


def host(brief: Dict) -> str:
    """index.html: the timeline every scene is mounted into."""
    d = identity_for(brief["theme"])
    lead, total = brief["lead"], brief["seconds"]
    narr = brief["narration"]["seconds"]
    slots = [_slot("intro", 0, lead)]
    caps = []
    for sc in brief["scenes"]:
        slots.append(_slot(scene_id(sc["n"]), lead + sc["start"], sc["seconds"]))
        for i, c in enumerate(sc["cues"]):
            caps.append(
                f'<div id="cap-{sc["n"]}-{i}" class="clip k-cap" data-start="{lead + c["t"]:.2f}" '
                f'data-duration="{c["d"]:.2f}" data-track-index="5"><span>{esc(c["text"])}</span></div>')
    slots.append(_slot("outro", lead + narr, brief["tail"]))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width={WIDTH}, height={HEIGHT}"/>
<title>{esc(brief['title'])}</title>
<script src="{GSAP}"></script>
{_fonts(d)}
<style>{_css(d)}</style>
</head><body>
<div id="root" data-composition-id="main" data-start="0" data-width="{WIDTH}" data-height="{HEIGHT}" data-duration="{total:.2f}">
  <div id="k-bg"></div>
  <audio id="narration" src="assets/narration.mp3" data-start="{lead:.2f}" data-duration="{narr:.2f}" data-track-index="0" data-volume="1"></audio>
  {chr(10).join('  ' + s for s in slots)}
  {chr(10).join('  ' + c for c in caps)}
  <div id="k-chrome"><div id="k-bug">HN.FM</div><div id="k-track"><div id="k-bar"></div></div></div>
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  tl.fromTo("#k-bar", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {total:.2f}, ease: "none" }}, 0);
  window.__timelines["main"] = tl;
</script>
</body></html>
"""


def _slot(cid: str, start: float, seconds: float) -> str:
    return (f'<div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
            f'data-start="{start:.2f}" data-duration="{seconds:.2f}" data-track-index="1" '
            f'data-width="{WIDTH}" data-height="{HEIGHT}"></div>')


def wrap(cid: str, style: str, body: str, script: str) -> str:
    """One scene file: a template holding its style, its root and its timeline."""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"/></head><body>
<template>
<style>{style}</style>
<div id="{cid}-root" class="k-scene" data-composition-id="{cid}" data-width="{WIDTH}" data-height="{HEIGHT}">
{body}
</div>
<script>
(function () {{
  const tl = gsap.timeline({{ paused: true }});
{script}
  window.__timelines["{cid}"] = tl;
}})();
</script>
</template>
</body></html>
"""


def intro(brief: Dict) -> str:
    meta = " · ".join(x for x in (
        brief.get("domain"),
        f'{brief["points"]} points' if (brief.get("points") or 0) >= 5 else "",
        f'{brief["comments"]} comments' if (brief.get("comments") or 0) >= 5 else "") if x)
    thumb = ('<img id="intro-thumb" src="assets/thumb.jpg" alt=""/>' if brief.get("has_thumb") else "")
    style = """
#intro-root .k-safe{height:592px;top:64px}
#intro-thumb{position:absolute;right:80px;top:150px;width:420px;height:262px;object-fit:cover;
  object-position:top;border-radius:14px;border:3px solid var(--accent)}
#intro-title{max-width:%dpx;font-size:%dpx}
""" % (640 if thumb else 1040, 60 if len(brief["title"]) > 60 else 72)
    body = f"""  {thumb}
  <div class="k-safe">
    <p id="intro-kicker" class="k-kicker">From the front page</p>
    <h1 id="intro-title" class="k-title">{esc(brief['title'])}</h1>
    <div id="intro-rule" class="k-rule"></div>
    <p id="intro-meta" class="k-body k-muted">{esc(meta)}</p>
  </div>"""
    script = """  tl.fromTo("#intro-title", { y: 26, opacity: 0.55 }, { y: 0, opacity: 1, duration: 0.7, ease: "power3.out" }, 0);
  tl.fromTo("#intro-rule", { scaleX: 0, transformOrigin: "0 50%" }, { scaleX: 1, duration: 0.6, ease: "power2.out" }, 0.3);
  tl.fromTo("#intro-meta", { opacity: 0 }, { opacity: 1, duration: 0.5 }, 0.6);""" + (
        '\n  tl.fromTo("#intro-thumb", { scale: 0.94, opacity: 0.4 }, { scale: 1, opacity: 1, duration: 0.8, ease: "power2.out" }, 0.1);'
        if thumb else "")
    return wrap("intro", style, body, script)


def outro(brief: Dict, credits: str = "") -> str:
    style = "#outro-url{font-size:40px;color:var(--accent);font-weight:600}"
    body = f"""  <div class="k-safe" style="height:592px">
    <p class="k-kicker">Read it, then read the comments</p>
    <p id="outro-url" class="k-body">{esc(brief.get('domain') or '')}</p>
    <p id="outro-hn" class="k-body">news.ycombinator.com/item?id={esc(brief['item_id'])}</p>
    <div id="outro-rule" class="k-rule"></div>
    <p id="outro-credit" class="k-body k-muted" style="font-size:24px">{esc(credits)}</p>
  </div>"""
    script = """  tl.fromTo("#outro-url", { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, 0.1);
  tl.fromTo("#outro-hn", { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, 0.3);
  tl.fromTo("#outro-rule", { scaleX: 0, transformOrigin: "0 50%" }, { scaleX: 1, duration: 0.5 }, 0.5);
  tl.fromTo("#outro-credit", { opacity: 0 }, { opacity: 1, duration: 0.5 }, 0.8);"""
    return wrap("outro", style, body, script)


def plain_scene(sc: Dict) -> str:
    """A scene nobody wrote: the still (if the story has one) drifting
    slowly, the beat as a chip, and the figure the line turns on, if it
    names one. It is what a scene falls back to, so it has to hold up."""
    cid = scene_id(sc["n"])
    secs = sc["seconds"]
    m = _NUMBER.search(sc["text"])
    figure = m.group(1).strip() if m and any(ch.isdigit() for ch in m.group(1)) and len(m.group(1).strip()) > 1 else ""
    beat = (sc.get("beat") or "").replace("_", " ").strip()
    img = sc.get("asset")
    parts, script = [], []
    if img:
        parts.append(f'  <img id="{cid}-img" class="k-img" src="{img}" alt=""/>\n  <div class="k-shade"></div>')
        script.append(f'  tl.fromTo("#{cid}-img", {{ scale: 1.0 }}, {{ scale: 1.08, duration: {secs:.2f}, ease: "none" }}, 0);')
    inner = []
    if beat:
        inner.append(f'<span id="{cid}-chip" class="k-chip">{esc(beat)}</span>')
        script.append(f'  tl.fromTo("#{cid}-chip", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, 0.2);')
    if figure:
        inner.append(f'<p id="{cid}-fig" class="k-stat" style="font-size:150px">{esc(figure)}</p>')
        script.append(f'  tl.fromTo("#{cid}-fig", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.6, ease: "power3.out" }}, 0.4);')
    if not img and not figure:
        lead_words = " ".join(sc["text"].split()[:9])
        inner.append(f'<p id="{cid}-line" class="k-title" style="font-size:60px">{esc(lead_words)}</p>')
        script.append(f'  tl.fromTo("#{cid}-line", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.6, ease: "power3.out" }}, 0.2);')
    if inner:
        box = ('<div class="k-card" style="align-self:flex-start;display:flex;flex-direction:column;gap:14px">'
               if img else '<div style="display:flex;flex-direction:column;gap:18px;align-items:flex-start">')
        # Over a picture the words sit low, clear of a two-line caption;
        # with nothing behind them they take the middle of the frame.
        place = "justify-content:flex-end;padding-bottom:40px;box-sizing:border-box" if img else "justify-content:center"
        parts.append(f'  <div class="k-safe" style="{place}">' + box + "".join(inner) + "</div></div>")
    return wrap(cid, "", "\n".join(parts), "\n".join(script))


def build(brief: Dict, project: str) -> Dict:
    """Write the whole project with plain scenes. Returns the brief with
    the asset paths a scene may use filled in."""
    os.makedirs(os.path.join(project, "compositions"), exist_ok=True)
    assets = os.path.join(project, "assets")
    os.makedirs(assets, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", brief["narration"]["path"], "-ac", "1",
                    "-b:a", "96k", os.path.join(assets, "narration.mp3")], check=True, timeout=300)
    brief = dict(brief)
    brief["has_thumb"] = bool(brief.get("thumb")) and _picture(brief["thumb"], os.path.join(assets, "thumb.jpg"), 840)
    for sc in brief["scenes"]:
        name = f"still-{sc['n']:02d}.jpg"
        sc["asset"] = f"assets/{name}" if sc.get("image") and _picture(sc["image"], os.path.join(assets, name), WIDTH) else None
    _write(project, "index.html", host(brief))
    _write(project, "compositions/intro.html", intro(brief))
    _write(project, "compositions/outro.html", outro(brief))
    for sc in brief["scenes"]:
        _write(project, scene_file(sc["n"]), plain_scene(sc))
    with open(os.path.join(project, "brief.json"), "w") as f:
        json.dump(brief, f, indent=1)
    return brief


def _picture(src: str, dst: str, width: int) -> bool:
    """A JPEG no wider than the canvas: stills arrive as multi-megabyte PNGs."""
    try:
        from PIL import Image

        img = Image.open(src).convert("RGB")
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)))
        img.save(dst, "JPEG", quality=86)
        return True
    except Exception:
        return False


def _write(project: str, rel: str, text: str) -> None:
    path = os.path.join(project, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def write_scene(project: str, n: int, text: str) -> None:
    _write(project, scene_file(n), text)


def keep_plain(project: str, n: int) -> None:
    """Remember the plain version so a rejected scene can be put back."""
    src = os.path.join(project, scene_file(n))
    dst = os.path.join(project, "plain", f"{scene_id(n)}.html")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst):
        shutil.copy(src, dst)


def restore_plain(project: str, n: int) -> None:
    src = os.path.join(project, "plain", f"{scene_id(n)}.html")
    if os.path.exists(src):
        shutil.copy(src, os.path.join(project, scene_file(n)))


def single(project: str, n: int, out: str) -> str:
    """A project holding one scene on its own, for checking it without
    rendering the rest: same head, same assets, one slot at zero."""
    with open(os.path.join(project, "brief.json")) as f:
        brief = json.load(f)
    sc = next(s for s in brief["scenes"] if s["n"] == n)
    d = identity_for(brief["theme"])
    os.makedirs(os.path.join(out, "compositions"), exist_ok=True)
    link = os.path.join(out, "assets")
    if not os.path.exists(link):
        os.symlink(os.path.join(project, "assets"), link)
    shutil.copy(os.path.join(project, scene_file(n)), os.path.join(out, scene_file(n)))
    _write(out, "index.html", f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width={WIDTH}, height={HEIGHT}"/>
<script src="{GSAP}"></script>
{_fonts(d)}
<style>{_css(d)}</style>
</head><body>
<div id="root" data-composition-id="main" data-start="0" data-width="{WIDTH}" data-height="{HEIGHT}" data-duration="{sc['seconds']:.2f}">
  <div id="k-bg"></div>
  {_slot(scene_id(n), 0, sc['seconds'])}
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  tl.to("#k-bg", {{ opacity: 1, duration: {sc['seconds']:.2f} }}, 0);
  window.__timelines["main"] = tl;
</script>
</body></html>
""")
    return out
