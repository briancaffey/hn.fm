"""The picture under every shot, and the panel the words sit on.

The first story videos put one card on a plain ground for a whole section,
with the section's still dimmed to 8% behind it: a slide deck. Here every
shot is a picture first. Each scene (one beat of narration, a few seconds)
gets one to three pictures that move the way a camera would (push, pull,
pan, rise), cut or dissolve inside the beat, and arrive through a
transition chosen for where the beat sits: a new section enters with a
whip, an iris or a dip; a beat inside a section with a blur swap or a push.

Words sit on a paper panel cut into the picture, revealed by a wipe, so the
picture and the words share the frame instead of the words hiding it. Words
said aloud are revealed when they are said (the recogniser's times), and a
number counts up to itself.

Everything is a function of timeline time: no timers, no randomness. The
choice of move and transition comes from the scene number.
"""

import json
import re
from typing import Dict, List, Optional, Tuple

from .kit import esc

# Camera moves for a picture: (from, to) GSAP vars. Scales stay above 1 so
# a pan never shows an edge.
MOVES: List[Tuple[Dict, Dict]] = [
    ({"scale": 1.04}, {"scale": 1.17}),                                  # push in
    ({"scale": 1.18}, {"scale": 1.05}),                                  # pull out
    ({"scale": 1.14, "xPercent": -3.2}, {"scale": 1.14, "xPercent": 3.2}),   # pan right
    ({"scale": 1.14, "xPercent": 3.2}, {"scale": 1.14, "xPercent": -3.2}),   # pan left
    ({"scale": 1.13, "yPercent": 3.0}, {"scale": 1.16, "yPercent": -3.0}),   # rise
    ({"scale": 1.10, "rotation": -0.8}, {"scale": 1.18, "rotation": 0.6}),  # drift
]

# How a scene arrives. A new section gets one of the first set; a beat
# inside a section one of the second. 3-5 kinds in a film, each with a cause.
SECTION_IN = ["whip", "iris", "dip", "whip_up"]
BEAT_IN = ["blur", "push", "blur", "cut"]


def _vars(d: Dict) -> str:
    return json.dumps(d).replace('"', "").replace(":", ": ").replace(",", ", ")


def entrance(sc: Dict) -> str:
    n = sc["n"]
    if sc.get("part", 1) == 1:
        return SECTION_IN[(sc.get("section") or n) % len(SECTION_IN)]
    return BEAT_IN[n % len(BEAT_IN)]


def plate(cid: str, sc: Dict) -> Tuple[str, List[str]]:
    """The pictures behind a scene, moved the way its form says, and the
    scene's entrance. Returns (markup, timeline lines)."""
    form = sc.get("form") or ("drift" if len(sc.get("shots") or []) > 1 else "drift")
    shots = [s for s in (sc.get("shots") or []) if s] or ([sc["asset"]] if sc.get("asset") else [])
    secs = float(sc["seconds"])
    html, js = [f'  <div id="{cid}-plate" class="k-plate" data-layout-allow-overflow>'], []
    if form == "type" or not shots:
        html.append(f'    <div id="{cid}-ground" class="k-ground"></div>')
        js.append(f'  tl.fromTo("#{cid}-ground", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.45, ease: "power3.inOut" }}, 0);')
    elif form == "split" and len(shots) >= 2:
        for i, src in enumerate(shots[:2]):
            side = "l" if i == 0 else "r"
            html.append(f'    <div id="{cid}-h{side}" class="k-half k-half-{side}"><img id="{cid}-s{i}" class="k-shot" style="opacity:1" src="{src}" alt=""/></div>')
            js.append(f'  tl.fromTo("#{cid}-h{side}", {{ xPercent: {-100 if i == 0 else 100} }}, {{ xPercent: 0, duration: 0.6, ease: "expo.out" }}, {0.05 + 0.18 * i:.2f});')
            js.append(f'  tl.fromTo("#{cid}-s{i}", {{ scale: 1.12 }}, {{ scale: 1.03, duration: {secs:.2f}, ease: "sine.out" }}, 0);')
    elif form == "sequence" and len(shots) >= 2:
        # Stop-motion: hard cuts between frames of one scene, the camera dead still.
        n = len(shots)
        step = secs / n
        for i, src in enumerate(shots):
            html.append(f'    <img id="{cid}-s{i}" class="k-shot" src="{src}" alt=""/>')
            js.append(f'  tl.set("#{cid}-s{i}", {{ opacity: 1, scale: 1.02 }}, {i * step:.2f});')
            if i + 1 < n:
                js.append(f'  tl.set("#{cid}-s{i}", {{ opacity: 0 }}, {(i + 1) * step:.2f});')
    elif form == "punch":
        fx, fy = sc.get("focus") or (50, 50)
        cut = round(min(max(1.2, secs * 0.45), secs - 1.0), 2)
        html.append(f'    <img id="{cid}-s0" class="k-shot" src="{shots[0]}" alt=""/>')
        js += [f'  tl.set("#{cid}-s0", {{ opacity: 1, scale: 1.0, transformOrigin: "{fx}% {fy}%" }}, 0);',
               f'  tl.set("#{cid}-s0", {{ scale: 1.85 }}, {cut:.2f});',
               f'  tl.fromTo("#{cid}-s0", {{ scale: 1.85 }}, {{ scale: 1.95, duration: {secs - cut + 0.3:.2f}, ease: "none", immediateRender: false }}, {cut:.2f});']
    else:
        if form in ("still", "drift", "pan"):
            shots = shots[:1]
        cuts = _cuts(sc, len(shots))
        for i, src in enumerate(shots):
            a = cuts[i]
            b = cuts[i + 1] if i + 1 < len(shots) else secs
            html.append(f'    <img id="{cid}-s{i}" class="k-shot" src="{src}" alt=""/>')
            frm, to = _move(form, sc["n"] + i)
            if form == "still":
                js.append(f'  tl.fromTo("#{cid}-s{i}", {_vars(frm)}, {{ ...{_vars(to)}, duration: 0.9, ease: "expo.out" }}, {a:.2f});')
            else:
                js.append(f'  tl.fromTo("#{cid}-s{i}", {_vars(frm)}, {{ ...{_vars(to)}, duration: {b - a + 0.5:.2f}, ease: "sine.inOut" }}, {a:.2f});')
            if i == 0:
                js.append(f'  tl.set("#{cid}-s{i}", {{ opacity: 1 }}, 0);')
            else:
                js.append(f'  tl.fromTo("#{cid}-s{i}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.45, ease: "power1.inOut" }}, {a - 0.2:.2f});')
    html.append(f'    <div class="k-grade"></div>\n  </div>')
    html.append(f'  <div id="{cid}-dip" class="k-dip"></div>')
    js += _arrive(cid, "cut" if form in ("split", "type") else entrance(sc))
    return "\n".join(html), js


def _move(form: str, k: int) -> Tuple[Dict, Dict]:
    """The camera for one picture. Pans only when the form is a pan."""
    if form == "still":
        return {"scale": 1.04}, {"scale": 1.0}           # lands, then holds dead still
    if form == "pan":
        return MOVES[2 + k % 2]
    return [MOVES[0], MOVES[1], MOVES[4], MOVES[5]][k % 4]   # push, pull, rise, drift


def _cuts(sc: Dict, n: int) -> List[float]:
    """Where each picture starts: on a phrase boundary near an even split."""
    secs = float(sc["seconds"])
    if n <= 1:
        return [0.0]
    marks = [round(c["t"] - sc["start"], 2) for c in sc.get("cues") or []][1:]
    out = [0.0]
    for k in range(1, n):
        want = secs * k / n
        near = min(marks, key=lambda m: abs(m - want)) if marks else want
        t = near if abs(near - want) < secs / (2 * n) else want
        out.append(round(max(out[-1] + 1.2, min(t, secs - 1.0)), 2))
    return out


def _arrive(cid: str, kind: str) -> List[str]:
    p = f"#{cid}-plate"
    if kind == "whip":
        return [f'  tl.fromTo("{p}", {{ xPercent: 14, filter: "blur(18px)" }}, {{ xPercent: 0, filter: "blur(0px)", duration: 0.38, ease: "expo.out" }}, 0);']
    if kind == "whip_up":
        return [f'  tl.fromTo("{p}", {{ yPercent: 16, filter: "blur(16px)" }}, {{ yPercent: 0, filter: "blur(0px)", duration: 0.4, ease: "expo.out" }}, 0);']
    if kind == "iris":
        return [f'  tl.fromTo("{p}", {{ clipPath: "circle(0% at 62% 42%)" }}, {{ clipPath: "circle(120% at 62% 42%)", duration: 0.55, ease: "power2.in" }}, 0);']
    if kind == "dip":
        return [f'  tl.fromTo("#{cid}-dip", {{ opacity: 0.85 }}, {{ opacity: 0, duration: 0.3, ease: "power1.out" }}, 0);']
    if kind == "blur":
        return [f'  tl.fromTo("{p}", {{ filter: "blur(10px)", opacity: 0.55 }}, {{ filter: "blur(0px)", opacity: 1, duration: 0.24, ease: "power2.out" }}, 0);']
    if kind == "push":
        return [f'  tl.fromTo("{p}", {{ scale: 1.12 }}, {{ scale: 1, duration: 0.5, ease: "expo.out" }}, 0);']
    return []  # a hard cut


def panel(cid: str, inner: str, t: float, place: str = "left", extra_style: str = "") -> Tuple[str, List[str]]:
    """Paper cut into the picture, wiped in at `t`."""
    html = f'  <div id="{cid}-panel" class="k-panel k-{place}" style="{extra_style}">{inner}</div>'
    js = [f'  tl.fromTo("#{cid}-panel", {{ clipPath: "inset(0% 100% 0% 0% round 22px)" }}, '
          f'{{ clipPath: "inset(0% 0% 0% 0% round 22px)", duration: 0.55, ease: "expo.out" }}, {t:.2f});']
    return html, js


# ── Numbers that count ──────────────────────────────────────────────────

_NUM = re.compile(r"^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$")


def countable(value: str) -> Optional[Tuple[str, float, int, bool, str]]:
    """(prefix, number, decimals, commas, suffix) for a value that leads
    with a number, else None. A year is not counted up."""
    m = _NUM.match(value.strip())
    if not m:
        return None
    raw = m.group(2)
    num = float(raw.replace(",", ""))
    if re.fullmatch(r"(1[5-9]|20)\d\d", raw) and not m.group(3).strip():
        return None
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return m.group(1), num, decimals, "," in raw or num >= 10000, m.group(3)


def count_up(cid: str, el: str, value: str, t: float, secs: float, run: float = 1.4) -> List[str]:
    """Count `#el` up to `value` from `t`, as a function of the timeline's
    time so any frame renders on its own."""
    c = countable(value)
    if not c:
        return []
    pre, num, dec, commas, suf = c
    return [f"""  (function () {{
    const el = document.querySelector("#{el}"), o = {{ p: 0 }};
    const fmt = (x) => {json.dumps(pre)} + x.toLocaleString("en-US", {{ minimumFractionDigits: {dec}, maximumFractionDigits: {dec}, useGrouping: {str(commas).lower()} }}) + {json.dumps(suf)};
    tl.fromTo(o, {{ p: 0 }}, {{ p: 1, duration: {secs:.2f}, ease: "none", onUpdate: function () {{
      const k = Math.min(1, Math.max(0, (this.time() - {t:.2f}) / {run}));
      el.textContent = fmt({num} * (1 - Math.pow(1 - k, 3)));
    }} }}, 0);
  }})();"""]


# ── Words revealed as they are said ─────────────────────────────────────

def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def spoken_times(sc: Dict, words: List[str], start: float, gap: float) -> List[float]:
    """When each of `words` is said in the scene, matched in order against
    what the recogniser heard; words it misheard keep an even spacing."""
    heard = sc.get("words") or []
    out, j = [], 0
    for i, w in enumerate(words):
        want, t = _norm(w), None
        for k in range(j, min(len(heard), j + 14)):
            if want and (_norm(heard[k]["w"]) == want or (len(want) > 4 and _norm(heard[k]["w"])[:4] == want[:4])):
                t, j = heard[k]["t"], k + 1
                break
        if t is None:
            t = (out[-1] + gap) if out else start
        if out and t < out[-1] + 0.06:
            t = out[-1] + 0.06
        out.append(round(max(0.1, min(t, float(sc["seconds"]) - 0.5)), 2))
    return out


CSS = """
.k-plate{position:absolute;inset:0;overflow:hidden;background:var(--bg)}
.k-shot{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transform-origin:50% 50%}
.k-grade{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 45%,transparent 52%,rgba(0,0,0,.38) 100%)}
.k-dip{position:absolute;inset:0;background:#000;opacity:0;pointer-events:none}
.k-ground{position:absolute;inset:0;background:var(--accent);opacity:.14;transform-origin:0 50%}
.k-half{position:absolute;top:0;bottom:0;width:50%;overflow:hidden}
.k-half-l{left:0;border-right:4px solid var(--bg)}
.k-half-r{right:0;border-left:4px solid var(--bg)}
.k-panel{position:absolute;background:var(--paper);border-radius:22px;padding:30px 38px;
  box-shadow:0 24px 70px rgba(0,0,0,.30);display:flex;flex-direction:column;gap:14px}
.k-panel .k-kicker{font-size:19px}
.k-left{left:72px;top:96px;width:620px}
.k-right{right:72px;top:96px;width:620px}
.k-low{left:72px;bottom:168px;max-width:820px}
.k-wide{left:72px;right:72px;bottom:168px}
.k-mid{left:50%;top:50%;transform:translate(-50%,-62%);width:980px}
.k-top{left:72px;top:72px;max-width:900px}
.k-type{left:96px;right:96px;top:50%;transform:translateY(-62%);background:transparent;box-shadow:none;padding:0;zoom:1.45}
"""
