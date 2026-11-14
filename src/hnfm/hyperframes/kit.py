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
from dataclasses import replace
from typing import Dict, List, Optional

from .design_identity import DesignIdentity, identity_for as _theme_identity

# The renderer's review refuses text under 4.5:1 against the canvas (WCAG AA).
# Several themes put their accent on text at far less (claymation's orange on
# cream is 2.1:1), which failed every directed scene in that theme. So the
# accent and muted colours are moved toward black or white, keeping their hue,
# until they read. Fills (rules, bars) use the same colour, slightly deeper.
READABLE = 4.6


def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(colour: str, bg: str, minimum: float = READABLE) -> str:
    """`colour`, moved toward black on a light canvas or white on a dark
    one, just far enough to reach `minimum` contrast against `bg`."""
    if contrast(colour, bg) >= minimum:
        return colour
    target = 0 if _luminance(bg) > 0.18 else 255
    h = colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    for step in range(1, 21):
        t = step / 20
        mixed = "#" + "".join(f"{round(c + (target - c) * t):02x}" for c in rgb)
        if contrast(mixed, bg) >= minimum:
            return mixed
    return "#000000" if target == 0 else "#ffffff"


def identity_for(theme: str) -> DesignIdentity:
    """The theme, with its accent and muted colours made readable on its
    own background."""
    d = _theme_identity(theme)
    return replace(d, accent=readable(d.accent, d.bg), muted=readable(d.muted, d.bg))

GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
WIDTH, HEIGHT, FPS = 1280, 720, 24
# A music bed sits well under the voice.
MUSIC_VOLUME = 0.13
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
    h = d.bg.lstrip("#")
    paper = "rgba({},{},{},.93)".format(*(int(h[i:i + 2], 16) for i in (0, 2, 4)))
    from . import cinema
    return cinema.CSS + f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{d.bg};color:{d.fg};font-family:'{d.body_font}',system-ui,sans-serif;
  font-weight:{d.body_weight};-webkit-font-smoothing:antialiased}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;
  --bg:{d.bg};--ink:{d.fg};--muted:{d.muted};--accent:{d.accent};--veil:{veil};--panel:{panel};--paper:{paper};
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
.k-cap{{position:absolute;left:0;right:0;bottom:40px;display:flex;justify-content:center;z-index:40}}
.k-cap span{{max-width:980px;padding:8px 20px;border-radius:10px;background:rgba(10,10,12,.72);
  font-family:var(--body);font-weight:600;font-size:30px;line-height:1.25;text-align:center;color:#fafafa}}
#k-chrome{{position:absolute;inset:0;z-index:50;pointer-events:none}}
#k-bug{{position:absolute;right:28px;top:24px;padding:6px 12px 6px 16px;border-radius:8px;background:var(--veil);
  font-family:var(--body);font-weight:800;font-size:19px;letter-spacing:.3em;color:var(--ink)}}
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
    music = (f'<audio id="music" src="assets/music.mp3" data-start="0" data-duration="{total:.2f}" '
             f'data-track-index="2" data-volume="{MUSIC_VOLUME}"></audio>' if brief.get("has_music") else "")
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
  {music}
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
    """The title over the story's first picture, word by word."""
    from . import cinema
    meta = " · ".join(x for x in (
        brief.get("domain"),
        f'{brief["points"]} points' if (brief.get("points") or 0) >= 5 else "",
        f'{brief["comments"]} comments' if (brief.get("comments") or 0) >= 5 else "") if x)
    first = (brief["scenes"][0].get("shots") or [None])[0] if brief.get("scenes") else None
    sc = {"n": 0, "part": 1, "section": 3, "seconds": brief["lead"], "shots": [first] if first else [], "cues": []}
    back, back_js = cinema.plate("intro", sc)
    words = brief["title"].split()
    size = 60 if len(brief["title"]) > 60 else 70
    spans = "".join(f'<span class="tw" id="intro-w{i}">{esc(w)} </span>' for i, w in enumerate(words))
    style = f"#intro-title{{font-size:{size}px}}"
    inner = (f'<p id="intro-kicker" class="k-kicker">From the front page</p>'
             f'<h1 id="intro-title" class="k-title">{spans}</h1><div id="intro-rule" class="k-rule"></div>'
             f'<p id="intro-meta" class="k-body k-muted" style="font-size:24px">{esc(meta)}</p>')
    box, box_js = cinema.panel("intro", inner, 0.15, "left", "width:760px;top:120px")
    js = back_js + box_js + [f'  tl.fromTo("#intro-w{i}", {{ opacity: 0, filter: "blur(6px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.13 }}, {0.45 + i * 0.07:.2f});' for i in range(len(words))]
    end = len(words) * 0.07
    js += [f'  tl.fromTo("#intro-rule", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: 0.5, ease: "power2.out" }}, {0.6 + end:.2f});',
           f'  tl.fromTo("#intro-meta", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {0.8 + end:.2f});']
    return wrap("intro", style, back + "\n" + box, "\n".join(js))


def outro(brief: Dict, credits: str = "") -> str:
    from . import cinema
    last = next((sc["shots"][-1] for sc in reversed(brief.get("scenes") or []) if sc.get("shots")), None)
    sc = {"n": 1, "part": 1, "section": 2, "seconds": brief["tail"], "shots": [last] if last else [], "cues": []}
    back, back_js = cinema.plate("outro", sc)
    style = "#outro-url{font-size:36px;color:var(--accent);font-weight:600}"
    inner = f"""<p class="k-kicker">Read it, then read the comments</p>
    <p id="outro-url" class="k-body">{esc(brief.get('domain') or '')}</p>
    <p id="outro-hn" class="k-body" style="font-size:26px">news.ycombinator.com/item?id={esc(brief['item_id'])}</p>
    <div id="outro-rule" class="k-rule"></div>
    <p id="outro-credit" class="k-body k-muted" style="font-size:20px">{esc(credits)}</p>"""
    box, box_js = cinema.panel("outro", inner, 0.1, "left", "width:760px;top:150px")
    js = back_js + box_js + [
        '  tl.fromTo("#outro-url", { opacity: 0, filter: "blur(6px)" }, { opacity: 1, filter: "blur(0px)", duration: 0.2 }, 0.45);',
        '  tl.fromTo("#outro-hn", { opacity: 0 }, { opacity: 1, duration: 0.3 }, 0.6);',
        '  tl.fromTo("#outro-rule", { scaleX: 0, transformOrigin: "0 50%" }, { scaleX: 1, duration: 0.5 }, 0.7);',
        '  tl.fromTo("#outro-credit", { opacity: 0 }, { opacity: 1, duration: 0.4 }, 0.9)']
    return wrap("outro", style, back + "\n" + box, "\n".join(js) + ";")


def plain_scene(sc: Dict) -> str:
    """A scene nobody wrote: its pictures moving, and the figure the line
    turns on on a panel, if it names one. It is what a scene falls back
    to, so it has to hold up."""
    from . import cinema
    cid = scene_id(sc["n"])
    m = _NUMBER.search(sc["text"])
    figure = m.group(1).strip() if m and any(ch.isdigit() for ch in m.group(1)) and len(m.group(1).strip()) > 1 else ""
    back, js = cinema.plate(cid, sc)
    body = back
    if figure:
        box, box_js = cinema.panel(cid, f'<p id="{cid}-fig" class="k-stat" style="font-size:120px">{esc(figure)}</p>',
                                   0.5, "left" if sc["n"] % 2 else "right", "width:auto")
        body += "\n" + box
        js += box_js
    elif not sc.get("shots"):
        lead_words = " ".join(sc["text"].split()[:9])
        box, box_js = cinema.panel(cid, f'<p id="{cid}-line" class="k-title" style="font-size:56px">{esc(lead_words)}</p>', 0.2, "low")
        body += "\n" + box
        js += box_js
    return wrap(cid, "", body, "\n".join(js))


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
    copied: Dict[str, str] = {}

    def asset(src: Optional[str]) -> Optional[str]:
        if not src:
            return None
        if src not in copied:
            name = f"pic-{len(copied) + 1:03d}.jpg"
            copied[src] = f"assets/{name}" if _picture(src, os.path.join(assets, name), WIDTH) else ""
        return copied[src] or None

    for sc in brief["scenes"]:
        sc["shots"] = [a for a in (asset(p) for p in shot_sources(sc)) if a]
        sc["asset"] = sc["shots"][0] if sc["shots"] else None
    if brief.get("music_path") and os.path.exists(brief["music_path"]):
        shutil.copy(brief["music_path"], os.path.join(assets, "music.mp3"))
        brief["has_music"] = True
    _write(project, "index.html", host(brief))
    _write(project, "compositions/intro.html", intro(brief))
    _write(project, "compositions/outro.html", outro(brief))
    for sc in brief["scenes"]:
        _write(project, scene_file(sc["n"]), plain_scene(sc))
    with open(os.path.join(project, "brief.json"), "w") as f:
        json.dump(brief, f, indent=1)
    return brief


def shot_sources(sc: Dict) -> List[str]:
    """The pictures for a beat: its own picture first (drawn for its line),
    then its share of the section's frames, so a section's frames are spread
    over its beats instead of all landing on the first."""
    frames = sc.get("frames") or ([sc["image"]] if sc.get("image") else [])
    k, parts = sc.get("part", 1) - 1, max(1, sc.get("parts", 1))
    mine = [f for j, f in enumerate(frames) if j % parts == k]
    out = ([sc["picture"]] if sc.get("picture") else []) + mine
    if not out and frames:
        out = [frames[k % len(frames)]]
    # Three pictures at most: one every second or so is a montage.
    return out[:3 if sc["seconds"] >= 5.5 else 2]


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
