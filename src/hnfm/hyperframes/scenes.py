"""The treatments: the kinds of scene a story video can show.

A treatment is a layout and its motion, written once and tested, that
takes a few words or numbers and times them to the narration. The author
(Hermes) reads a line of narration and says which treatment it calls for
and what goes in it; nothing the author writes is markup.

This is the same split the radio settled on: code owns the shape, the
model supplies the words. Asked to write the markup itself, the local
model returned the worked example with a number of its own invention.
"""

import re
from typing import Callable, Dict, List, Optional, Tuple

from .kit import esc, scene_id, wrap

EASE = "power3.out"

# What each treatment takes. `need` must be present; `words` caps how much
# text a field may hold, because a scene is read in passing.
TREATMENTS: Dict[str, Dict] = {
    "figure": {
        "for": "the line turns on one number",
        "fields": {"value": "the number with its unit, as said (for example 64 GB)",
                   "label": "what it measures, two to five words",
                   "kicker": "optional: two or three words above it"},
        "need": ["value", "label"], "words": {"value": 3, "label": 7, "kicker": 4},
    },
    "compare": {
        "for": "two things set against each other",
        "fields": {"left": "{name, value}: the first thing and its number or one-to-three-word trait",
                   "right": "{name, value}: the second",
                   "title": "optional: what is being compared, up to five words"},
        "need": ["left", "right"], "words": {"title": 6},
    },
    "bars": {
        "for": "two to four numbers of the same kind",
        "fields": {"title": "what the numbers measure, up to six words",
                   "rows": "[{name, value}]: two to four rows, value a plain number, largest first or in the order said",
                   "unit": "optional: the unit all rows share (GB, ms, %)"},
        "need": ["title", "rows"], "words": {"title": 7, "unit": 2},
    },
    "list": {
        "for": "the line names several things",
        "fields": {"title": "optional: what the list is, up to five words",
                   "items": "two to four items, each two to five words, in the order said"},
        "need": ["items"], "words": {"title": 6},
    },
    "steps": {
        "for": "the line describes a sequence or how something works",
        "fields": {"title": "optional: up to five words",
                   "items": "two to four stages, each one to three words, in order"},
        "need": ["items"], "words": {"title": 6},
    },
    "phrase": {
        "for": "an opening, a turn or a closing line that should land",
        "fields": {"words": "the three to seven words that carry the line, taken from it",
                   "accent": "optional: the one word among them to pick out",
                   "kicker": "optional: two or three words above"},
        "need": ["words"], "words": {"words": 8, "kicker": 4},
    },
    "quote": {
        "for": "the line reports what someone said or claims",
        "fields": {"quote": "the claim in up to fourteen words, from the line",
                   "by": "who says it, if the line says"},
        "need": ["quote"], "words": {"quote": 16, "by": 5},
    },
    "picture": {
        "for": "the line describes a thing better seen than read (only when the scene has an image)",
        "fields": {"label": "what the picture shows, two to six words",
                   "kicker": "optional: two or three words above"},
        "need": ["label"], "words": {"label": 8, "kicker": 4},
    },
}

_STOP = set("a an and are as at be but by for from has have if in into is it its of on or than that the their then "
            "this to was were which while will with you your".split())


def _words(s: str) -> List[str]:
    return re.findall(r"[a-z0-9]+(?:[.'][a-z0-9]+)*", (s or "").lower())


def when(sc: Dict, phrase: str, default: float) -> float:
    """The second, from the start of the scene, at which `phrase` is spoken:
    the cue that shares most of its words, and how far into that cue."""
    want = [w for w in _words(phrase) if w not in _STOP]
    if not want:
        return default
    best, score = None, 0
    for c in sc["cues"]:
        have = _words(c["text"])
        hit = sum(1 for w in want if w in have)
        if hit > score:
            best, score = c, hit
    if not best:
        return default
    have = _words(best["text"])
    first = min((have.index(w) for w in want if w in have), default=0)
    t = best["t"] - sc["start"] + best["d"] * first / max(1, len(have))
    return round(max(0.15, min(t - 0.15, sc["seconds"] - 1.2)), 2)


def _spread(sc: Dict, items: List[str], lead: float = 0.3) -> List[float]:
    """A time for each item: where it is said, kept in order and apart."""
    n = len(items)
    even = [lead + i * max(0.6, (sc["seconds"] - 1.6) / max(1, n)) for i in range(n)]
    out = []
    for i, it in enumerate(items):
        t = when(sc, it, even[i])
        if out and t < out[-1] + 0.45:
            t = out[-1] + 0.45
        out.append(round(min(t, sc["seconds"] - 0.9), 2))
    return out


def _soon(t: float, sc: Dict, share: float = 0.35) -> float:
    """A cue time, but never so late that the frame sits empty: the main
    element is on screen within the first third of the scene."""
    return round(min(t, max(0.4, sc["seconds"] * share)), 2)


def _backdrop(cid: str, sc: Dict, strength: float = 0.08) -> Tuple[str, str]:
    """The scene's still, dimmed, behind a text treatment."""
    if not sc.get("asset"):
        return "", ""
    # Blurred as well as dimmed: many stills carry words of their own.
    body = (f'  <img id="{cid}-back" class="k-img" src="{sc["asset"]}" alt="" style="opacity:{strength};filter:blur(10px)"/>')
    js = (f'  tl.fromTo("#{cid}-back", {{ scale: 1.04 }}, {{ scale: 1.12, duration: {sc["seconds"]:.2f}, ease: "none" }}, 0);')
    return body, js


def _fit(text: str, steps: List[Tuple[int, int]]) -> int:
    """A font size for a string: the first (max characters, size) it fits."""
    n = len(text)
    for limit, size in steps:
        if n <= limit:
            return size
    return steps[-1][1]


def figure(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    value, label, kicker = str(c["value"]), str(c["label"]), str(c.get("kicker") or "")
    size = _fit(value, [(4, 250), (6, 210), (9, 160), (13, 120), (99, 92)])
    t = _soon(when(sc, value, 0.4), sc)
    back, back_js = _backdrop(cid, sc)
    body = f"""{back}
  <div class="k-safe">
    {f'<p id="{cid}-kick" class="k-kicker">{esc(kicker)}</p>' if kicker else ''}
    <p id="{cid}-val" class="k-stat" style="font-size:{size}px">{esc(value)}</p>
    <div id="{cid}-rule" class="k-rule"></div>
    <p id="{cid}-label" class="k-body" style="font-size:40px;max-width:900px">{esc(label)}</p>
  </div>"""
    js = [back_js] if back_js else []
    if kicker:
        js.append(f'  tl.fromTo("#{cid}-kick", {{ opacity: 0.5 }}, {{ opacity: 1, duration: 0.4 }}, 0);')
    js += [
        f'  tl.fromTo("#{cid}-val", {{ y: 70, opacity: 0, scale: 0.92, transformOrigin: "0 100%" }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.7, ease: "{EASE}" }}, {t});',
        f'  tl.fromTo("#{cid}-rule", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: 0.5, ease: "power2.out" }}, {t + 0.35:.2f});',
        f'  tl.fromTo("#{cid}-label", {{ y: 16, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: "{EASE}" }}, {min(0.3, t):.2f});',
    ]
    return wrap(cid, "", body, "\n".join(js))


def _num(s) -> Optional[float]:
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(s))
    return float(m.group(0).replace(",", "")) if m else None


def compare(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    left, right = c["left"], c["right"]
    title = str(c.get("title") or "")
    tl_, tr_ = _spread(sc, [f'{left["name"]} {left["value"]}', f'{right["name"]} {right["value"]}'], 0.4)
    tl_ = _soon(tl_, sc, 0.15)
    tr_ = max(tl_ + 0.5, _soon(tr_, sc, 0.55))
    a, b = _num(left["value"]), _num(right["value"])
    bars = a is not None and b is not None and max(a, b) > 0
    style = f"""
#{cid}-cols{{display:flex;gap:40px;align-items:stretch}}
#{cid}-l,#{cid}-r{{flex:1;display:flex;flex-direction:column;gap:12px;padding:30px 34px;border-radius:18px;
  background:var(--panel);border-top:8px solid var(--accent)}}
#{cid}-r{{border-top-color:var(--muted)}}
#{cid}-root .v{{font-family:var(--display);font-weight:800;line-height:1;letter-spacing:-.03em;margin:0;color:var(--ink)}}
#{cid}-root .n{{font-family:var(--body);font-weight:600;font-size:26px;letter-spacing:.14em;text-transform:uppercase;margin:0;color:var(--muted)}}
#{cid}-root .b{{height:16px;border-radius:8px;background:var(--accent);transform-origin:0 50%}}
#{cid}-r .b{{background:var(--muted)}}
"""
    def col(side, d, bar_pct):
        v = str(d["value"])
        size = _fit(v, [(5, 120), (9, 92), (16, 62), (99, 44)])
        bar = (f'<div id="{cid}-{side}b" class="b" style="width:{bar_pct}%"></div>' if bars else "")
        return (f'<div id="{cid}-{side}"><p class="n">{esc(d["name"])}</p>'
                f'<p class="v" style="font-size:{size}px">{esc(v)}</p>{bar}</div>')
    top = max(a or 0, b or 0) or 1
    body = f"""  <div class="k-safe">
    {f'<p id="{cid}-title" class="k-kicker">{esc(title)}</p>' if title else ''}
    <div id="{cid}-cols">{col('l', left, round(100 * (a or 0) / top))}{col('r', right, round(100 * (b or 0) / top))}</div>
  </div>"""
    js = []
    if title:
        js.append(f'  tl.fromTo("#{cid}-title", {{ opacity: 0.5 }}, {{ opacity: 1, duration: 0.4 }}, 0);')
    for side, t in (("l", tl_), ("r", tr_)):
        js.append(f'  tl.fromTo("#{cid}-{side}", {{ y: 50, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.6, ease: "{EASE}" }}, {t});')
        if bars:
            js.append(f'  tl.fromTo("#{cid}-{side}b", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.8, ease: "power2.out" }}, {t + 0.3:.2f});')
    return wrap(cid, style, body, "\n".join(js))


def bars(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    rows = c["rows"][:4]
    unit = str(c.get("unit") or "")
    top = max((_num(r["value"]) or 0) for r in rows) or 1
    times = _spread(sc, [f'{r["name"]} {r["value"]}' for r in rows], 0.5)
    times[0] = _soon(times[0], sc, 0.15)
    style = f"""
#{cid}-rows{{display:flex;flex-direction:column;gap:26px;margin-top:10px}}
#{cid}-root .row{{display:grid;grid-template-columns:300px 1fr;align-items:center;gap:24px}}
#{cid}-root .name{{font-family:var(--body);font-weight:600;font-size:32px;margin:0;color:var(--ink)}}
#{cid}-root .track{{display:flex;align-items:center;gap:20px}}
#{cid}-root .bar{{height:60px;border-radius:10px;background:var(--accent);transform-origin:0 50%}}
#{cid}-root .val{{font-family:var(--display);font-weight:800;font-size:46px;margin:0;color:var(--ink);white-space:nowrap}}
"""
    out, js = [], [f'  tl.fromTo("#{cid}-title", {{ y: 20, opacity: 0.4 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: "{EASE}" }}, 0);']
    for i, r in enumerate(rows):
        pct = max(4, round(100 * (_num(r["value"]) or 0) / top))
        v = f'{r["value"]}{" " + unit if unit and unit.lower() not in str(r["value"]).lower() else ""}'
        out.append(f'<div class="row" id="{cid}-row{i}"><p class="name">{esc(r["name"])}</p><div class="track">'
                   f'<div class="bar" id="{cid}-bar{i}" style="width:{pct * 0.62:.1f}%"></div>'
                   f'<p class="val" id="{cid}-val{i}">{esc(v)}</p></div></div>')
        js.append(f'  tl.fromTo("#{cid}-row{i}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {times[i]});')
        js.append(f'  tl.fromTo("#{cid}-bar{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.8, ease: "power2.out" }}, {times[i]});')
        js.append(f'  tl.fromTo("#{cid}-val{i}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {times[i] + 0.5:.2f});')
    body = f"""  <div class="k-safe">
    <p id="{cid}-title" class="k-title" style="font-size:48px">{esc(c['title'])}</p>
    <div id="{cid}-rows">{''.join(out)}</div>
  </div>"""
    return wrap(cid, style, body, "\n".join(js))


def listing(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    items = [str(x) for x in c["items"][:4]]
    title = str(c.get("title") or "")
    times = _spread(sc, items, 0.5)
    times[0] = _soon(times[0], sc, 0.15)
    size = 46 if max(len(i) for i in items) <= 26 else 38
    style = f"""
#{cid}-items{{display:flex;flex-direction:column;gap:18px}}
#{cid}-root .it{{display:flex;align-items:baseline;gap:24px}}
#{cid}-root .no{{font-family:var(--body);font-weight:600;font-size:24px;letter-spacing:.1em;color:var(--accent);margin:0;min-width:44px}}
#{cid}-root .tx{{font-family:var(--display);font-weight:800;font-size:{size}px;line-height:1.1;letter-spacing:-.02em;margin:0;color:var(--ink)}}
"""
    back, back_js = _backdrop(cid, sc)
    rows, js = [], ([back_js] if back_js else [])
    if title:
        js.append(f'  tl.fromTo("#{cid}-title", {{ opacity: 0.5 }}, {{ opacity: 1, duration: 0.4 }}, 0);')
    for i, it in enumerate(items):
        rows.append(f'<div class="it" id="{cid}-it{i}"><p class="no">{i + 1:02d}</p><p class="tx">{esc(it)}</p></div>')
        js.append(f'  tl.fromTo("#{cid}-it{i}", {{ x: -40, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.55, ease: "{EASE}" }}, {times[i]});')
    body = f"""{back}
  <div class="k-safe">
    {f'<p id="{cid}-title" class="k-kicker">{esc(title)}</p>' if title else ''}
    <div id="{cid}-items">{''.join(rows)}</div>
  </div>"""
    return wrap(cid, style, body, "\n".join(js))


def steps(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    items = [str(x) for x in c["items"][:4]]
    title = str(c.get("title") or "")
    times = _spread(sc, items, 0.5)
    times[0] = _soon(times[0], sc, 0.15)
    size = 36 if max(len(i) for i in items) <= 14 else 28
    style = f"""
#{cid}-flow{{display:flex;align-items:center;gap:0}}
#{cid}-root .st{{flex:1;min-height:150px;display:flex;align-items:center;justify-content:center;text-align:center;
  padding:22px 18px;border-radius:18px;border:3px solid var(--accent);background:var(--panel)}}
#{cid}-root .st p{{font-family:var(--display);font-weight:800;font-size:{size}px;line-height:1.1;margin:0;color:var(--ink)}}
#{cid}-root .ar{{width:54px;height:6px;background:var(--accent);transform-origin:0 50%;flex:none}}
"""
    parts, js = [], []
    if title:
        js.append(f'  tl.fromTo("#{cid}-title", {{ opacity: 0.5 }}, {{ opacity: 1, duration: 0.4 }}, 0);')
    for i, it in enumerate(items):
        if i:
            parts.append(f'<div class="ar" id="{cid}-ar{i}"></div>')
            js.append(f'  tl.fromTo("#{cid}-ar{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.35, ease: "power2.out" }}, {max(0.1, times[i] - 0.3):.2f});')
        parts.append(f'<div class="st" id="{cid}-st{i}"><p>{esc(it)}</p></div>')
        js.append(f'  tl.fromTo("#{cid}-st{i}", {{ scale: 0.86, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "back.out(1.4)" }}, {times[i]});')
    body = f"""  <div class="k-safe">
    {f'<p id="{cid}-title" class="k-kicker">{esc(title)}</p>' if title else ''}
    <div id="{cid}-flow">{''.join(parts)}</div>
  </div>"""
    return wrap(cid, style, body, "\n".join(js))


def phrase(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    words = str(c["words"]).split()
    accent = str(c.get("accent") or "").strip(".,;:!?").lower()
    kicker = str(c.get("kicker") or "")
    size = _fit(" ".join(words), [(14, 136), (22, 112), (34, 92), (48, 76), (99, 62)])
    t0 = _soon(when(sc, " ".join(words), 0.3), sc, 0.2)
    style = f"""
#{cid}-line{{display:flex;flex-wrap:wrap;gap:0 {round(size * 0.26)}px;max-width:1080px}}
#{cid}-root .w{{display:block;font-family:var(--display);font-weight:800;font-size:{size}px;line-height:1.04;
  letter-spacing:-.035em;margin:0;color:var(--ink)}}
#{cid}-root .w.hi{{color:var(--accent)}}
"""
    back, back_js = _backdrop(cid, sc, 0.10)
    spans, js = [], ([back_js] if back_js else [])
    if kicker:
        js.append(f'  tl.fromTo("#{cid}-kick", {{ opacity: 0.5 }}, {{ opacity: 1, duration: 0.4 }}, 0);')
    gap = min(0.22, max(0.1, (sc["seconds"] - t0 - 1.5) / max(1, len(words))))
    for i, w in enumerate(words):
        hi = " hi" if accent and w.strip(".,;:!?").lower() == accent else ""
        spans.append(f'<p class="w{hi}" id="{cid}-w{i}">{esc(w)}</p>')
        js.append(f'  tl.fromTo("#{cid}-w{i}", {{ y: 44, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.5, ease: "{EASE}" }}, {t0 + i * gap:.2f});')
    js.append(f'  tl.fromTo("#{cid}-rule", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: 0.6, ease: "power2.out" }}, {t0 + len(words) * gap + 0.1:.2f});')
    body = f"""{back}
  <div class="k-safe">
    {f'<p id="{cid}-kick" class="k-kicker">{esc(kicker)}</p>' if kicker else ''}
    <div id="{cid}-line">{''.join(spans)}</div>
    <div id="{cid}-rule" class="k-rule"></div>
  </div>"""
    return wrap(cid, style, body, "\n".join(js))


def quote(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    q, by = str(c["quote"]).strip('"“” '), str(c.get("by") or "")
    size = _fit(q, [(50, 66), (80, 54), (120, 44), (999, 38)])
    t0 = _soon(when(sc, q, 0.4), sc, 0.2)
    style = f"""
#{cid}-mark{{font-family:var(--display);font-weight:800;font-size:220px;line-height:.6;color:var(--accent);margin:0;height:90px}}
#{cid}-q{{font-family:var(--display);font-weight:600;font-size:{size}px;line-height:1.18;letter-spacing:-.02em;
  margin:0;color:var(--ink);max-width:1040px}}
"""
    back, back_js = _backdrop(cid, sc)
    js = ([back_js] if back_js else []) + [
        f'  tl.fromTo("#{cid}-mark", {{ opacity: 0.35 }}, {{ opacity: 1, duration: 0.5 }}, 0);',
        f'  tl.fromTo("#{cid}-q", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.7, ease: "{EASE}" }}, {t0});',
    ]
    if by:
        js.append(f'  tl.fromTo("#{cid}-by", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, {t0 + 0.8:.2f});')
    body = f"""{back}
  <div class="k-safe">
    <p id="{cid}-mark">&ldquo;</p>
    <p id="{cid}-q">{esc(q)}</p>
    {f'<p id="{cid}-by" class="k-kicker">{esc(by)}</p>' if by else ''}
  </div>"""
    return wrap(cid, style, body, "\n".join(js))


def picture(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    label, kicker = str(c["label"]), str(c.get("kicker") or "")
    t0 = _soon(when(sc, label, 0.6), sc, 0.25)
    style = f"""
#{cid}-card{{align-self:flex-start;display:flex;flex-direction:column;gap:10px;max-width:820px}}
#{cid}-label{{font-family:var(--display);font-weight:800;font-size:{_fit(label, [(24, 56), (40, 46), (99, 38)])}px;line-height:1.08;
  letter-spacing:-.02em;margin:0;color:var(--ink)}}
"""
    body = f"""  <img id="{cid}-img" class="k-img" src="{sc['asset']}" alt=""/>
  <div class="k-shade"></div>
  <div class="k-safe" style="justify-content:flex-end">
    <div id="{cid}-card" class="k-card">
      {f'<p id="{cid}-kick" class="k-kicker">{esc(kicker)}</p>' if kicker else ''}
      <p id="{cid}-label">{esc(label)}</p>
    </div>
  </div>"""
    js = [
        f'  tl.fromTo("#{cid}-img", {{ scale: 1.0 }}, {{ scale: 1.1, duration: {sc["seconds"]:.2f}, ease: "none" }}, 0);',
        f'  tl.fromTo("#{cid}-card", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.6, ease: "{EASE}" }}, {t0});',
    ]
    return wrap(cid, style, body, "\n".join(js))


BUILD: Dict[str, Callable[[Dict, Dict], str]] = {
    "figure": figure, "compare": compare, "bars": bars, "list": listing,
    "steps": steps, "phrase": phrase, "quote": quote, "picture": picture,
}


def build(sc: Dict, card: Dict) -> str:
    """The scene file for a storyboard card (already validated)."""
    return BUILD[card["treatment"]](sc, card)


def menu(has_image: bool) -> str:
    """The treatments as the author is shown them."""
    lines = []
    for name, t in TREATMENTS.items():
        if name == "picture" and not has_image:
            continue
        fields = "; ".join(f"`{k}`: {v}" for k, v in t["fields"].items())
        lines.append(f"- `{name}`: {t['for']}. Fields: {fields}.")
    return "\n".join(lines)
