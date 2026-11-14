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

from . import cinema
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


def _fit(text: str, steps: List[Tuple[int, int]]) -> int:
    """A font size for a string: the first (max characters, size) it fits."""
    n = len(text)
    for limit, size in steps:
        if n <= limit:
            return size
    return steps[-1][1]


def _num(s) -> Optional[float]:
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(s))
    return float(m.group(0).replace(",", "")) if m else None


def _side(sc: Dict) -> str:
    """Panels alternate sides so consecutive shots do not stack the same way."""
    return "left" if sc["n"] % 2 else "right"


def _scene(cid: str, sc: Dict, style: str, inner: str, t: float, place: str, js: List[str],
           panel_style: str = "") -> str:
    back, back_js = cinema.plate(cid, sc)
    box, box_js = cinema.panel(cid, inner, t, place, panel_style)
    return wrap(cid, style, back + "\n" + box, "\n".join(back_js + box_js + js))


def figure(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    value, label, kicker = str(c["value"]), str(c["label"]), str(c.get("kicker") or "")
    size = _fit(value, [(4, 168), (6, 140), (9, 112), (13, 86), (99, 66)])
    t = _soon(when(sc, value, 0.4), sc)
    inner = (f'{f"<p id={chr(34)}{cid}-kick{chr(34)} class={chr(34)}k-kicker{chr(34)}>{esc(kicker)}</p>" if kicker else ""}'
             f'<p id="{cid}-val" class="k-stat" style="font-size:{size}px;font-variant-numeric:tabular-nums">{esc(value)}</p>'
             f'<div id="{cid}-rule" class="k-rule"></div>'
             f'<p id="{cid}-label" class="k-body" style="font-size:34px">{esc(label)}</p>')
    js = [
        f'  tl.fromTo("#{cid}-val", {{ y: 34, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.6, ease: "expo.out" }}, {t + 0.15:.2f});',
        f'  tl.fromTo("#{cid}-rule", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: 0.5, ease: "power2.out" }}, {t + 0.5:.2f});',
        f'  tl.fromTo("#{cid}-label", {{ opacity: 0, filter: "blur(6px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.25 }}, {t + 0.7:.2f});',
    ] + cinema.count_up(cid, f"{cid}-val", value, t + 0.15, sc["seconds"])
    return _scene(cid, sc, "", inner, max(0.1, t - 0.25), _side(sc), js)


def compare(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    left, right = c["left"], c["right"]
    title = str(c.get("title") or "")
    tl_, tr_ = _spread(sc, [f'{left["name"]} {left["value"]}', f'{right["name"]} {right["value"]}'], 0.4)
    tl_ = _soon(tl_, sc, 0.15)
    tr_ = max(tl_ + 0.5, _soon(tr_, sc, 0.55))
    a, b = _num(left["value"]), _num(right["value"])
    bars_on = a is not None and b is not None and max(a, b) > 0
    style = f"""
#{cid}-cols{{display:flex;gap:28px;align-items:stretch}}
#{cid}-l,#{cid}-r{{flex:1;display:flex;flex-direction:column;gap:10px;padding:6px 0 0 22px;border-left:6px solid var(--accent)}}
#{cid}-r{{border-left-color:var(--muted)}}
#{cid}-root .v{{font-family:var(--display);font-weight:800;line-height:1;letter-spacing:-.03em;margin:0;color:var(--ink)}}
#{cid}-root .n{{font-family:var(--body);font-weight:600;font-size:21px;letter-spacing:.14em;text-transform:uppercase;margin:0;color:var(--muted)}}
#{cid}-root .b{{height:14px;border-radius:7px;background:var(--accent);transform-origin:0 50%}}
#{cid}-r .b{{background:var(--muted)}}
"""
    top = max(a or 0, b or 0) or 1

    def col(side, d, pct):
        v = str(d["value"])
        size = _fit(v, [(5, 92), (9, 70), (16, 50), (99, 38)])
        bar = f'<div id="{cid}-{side}b" class="b" style="width:{pct}%"></div>' if bars_on else ""
        return (f'<div id="{cid}-{side}"><p class="n">{esc(d["name"])}</p>'
                f'<p class="v" style="font-size:{size}px">{esc(v)}</p>{bar}</div>')
    inner = (f'{f"<p id={chr(34)}{cid}-title{chr(34)} class={chr(34)}k-kicker{chr(34)}>{esc(title)}</p>" if title else ""}'
             f'<div id="{cid}-cols">{col("l", left, round(100 * (a or 0) / top))}{col("r", right, round(100 * (b or 0) / top))}</div>')
    js = []
    for side, t in (("l", tl_), ("r", tr_)):
        js.append(f'  tl.fromTo("#{cid}-{side}", {{ x: 30, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.55, ease: "expo.out" }}, {t + 0.2:.2f});')
        if bars_on:
            js.append(f'  tl.fromTo("#{cid}-{side}b", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.8, ease: "power2.out" }}, {t + 0.45:.2f});')
    return _scene(cid, sc, style, inner, max(0.1, tl_ - 0.2), "low", js, "width:860px")


def bars(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    rows = c["rows"][:4]
    unit = str(c.get("unit") or "")
    top = max((_num(r["value"]) or 0) for r in rows) or 1
    times = _spread(sc, [f'{r["name"]} {r["value"]}' for r in rows], 0.5)
    times[0] = _soon(times[0], sc, 0.15)
    style = f"""
#{cid}-rows{{display:flex;flex-direction:column;gap:16px;margin-top:4px}}
#{cid}-root .row{{display:grid;grid-template-columns:190px 1fr;align-items:center;gap:18px}}
#{cid}-root .name{{font-family:var(--body);font-weight:600;font-size:24px;margin:0;color:var(--ink)}}
#{cid}-root .track{{display:flex;align-items:center;gap:14px}}
#{cid}-root .bar{{height:40px;border-radius:8px;background:var(--accent);transform-origin:0 50%}}
#{cid}-root .val{{font-family:var(--display);font-weight:800;font-size:32px;margin:0;color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums}}
"""
    out, js = [], []
    for i, r in enumerate(rows):
        pct = max(4, round(100 * (_num(r["value"]) or 0) / top))
        v = f'{r["value"]}{" " + unit if unit and unit.lower() not in str(r["value"]).lower() else ""}'
        out.append(f'<div class="row" id="{cid}-row{i}"><p class="name">{esc(r["name"])}</p><div class="track">'
                   f'<div class="bar" id="{cid}-bar{i}" style="width:{pct * 0.55:.1f}%"></div>'
                   f'<p class="val" id="{cid}-val{i}">{esc(v)}</p></div></div>')
        t = times[i] + 0.2
        js.append(f'  tl.fromTo("#{cid}-row{i}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25 }}, {t:.2f});')
        js.append(f'  tl.fromTo("#{cid}-bar{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.9, ease: "power3.out" }}, {t:.2f});')
        js += cinema.count_up(cid, f"{cid}-val{i}", v, t, sc["seconds"], 0.9)
    inner = (f'<p id="{cid}-title" class="k-title" style="font-size:38px">{esc(c["title"])}</p>'
             f'<div id="{cid}-rows">{"".join(out)}</div>')
    return _scene(cid, sc, style, inner, max(0.1, times[0] - 0.2), _side(sc), js, "width:700px")


def listing(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    items = [str(x) for x in c["items"][:4]]
    title = str(c.get("title") or "")
    times = _spread(sc, items, 0.5)
    times[0] = _soon(times[0], sc, 0.15)
    size = 38 if max(len(i) for i in items) <= 22 else 32
    style = f"""
#{cid}-items{{display:flex;flex-direction:column;gap:12px}}
#{cid}-root .it{{display:flex;align-items:baseline;gap:18px}}
#{cid}-root .no{{font-family:var(--body);font-weight:600;font-size:20px;letter-spacing:.1em;color:var(--accent);margin:0;min-width:34px}}
#{cid}-root .tx{{font-family:var(--display);font-weight:800;font-size:{size}px;line-height:1.08;letter-spacing:-.02em;margin:0;color:var(--ink)}}
"""
    rows, js = [], []
    for i, it in enumerate(items):
        rows.append(f'<div class="it" id="{cid}-it{i}"><p class="no">{i + 1:02d}</p><p class="tx">{esc(it)}</p></div>')
        js.append(f'  tl.fromTo("#{cid}-it{i}", {{ opacity: 0, filter: "blur(6px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.2 }}, {times[i] + 0.1:.2f});')
    inner = (f'{f"<p id={chr(34)}{cid}-title{chr(34)} class={chr(34)}k-kicker{chr(34)}>{esc(title)}</p>" if title else ""}'
             f'<div id="{cid}-items">{"".join(rows)}</div>')
    return _scene(cid, sc, style, inner, max(0.1, times[0] - 0.3), _side(sc), js)


def steps(sc: Dict, c: Dict) -> str:
    cid = scene_id(sc["n"])
    items = [str(x) for x in c["items"][:4]]
    title = str(c.get("title") or "")
    times = _spread(sc, items, 0.5)
    times[0] = _soon(times[0], sc, 0.15)
    size = 30 if max(len(i) for i in items) <= 14 else 24
    style = f"""
#{cid}-flow{{display:flex;align-items:center;gap:0}}
#{cid}-root .st{{flex:1;min-height:110px;display:flex;align-items:center;justify-content:center;text-align:center;
  padding:16px 14px;border-radius:16px;border:3px solid var(--accent)}}
#{cid}-root .st p{{font-family:var(--display);font-weight:800;font-size:{size}px;line-height:1.1;margin:0;color:var(--ink)}}
#{cid}-root .ar{{width:40px;height:5px;background:var(--accent);transform-origin:0 50%;flex:none}}
"""
    parts, js = [], []
    for i, it in enumerate(items):
        if i:
            parts.append(f'<div class="ar" id="{cid}-ar{i}"></div>')
            js.append(f'  tl.fromTo("#{cid}-ar{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.3, ease: "power2.out" }}, {max(0.2, times[i] - 0.2):.2f});')
        parts.append(f'<div class="st" id="{cid}-st{i}"><p>{esc(it)}</p></div>')
        js.append(f'  tl.fromTo("#{cid}-st{i}", {{ scale: 0.9, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.4)" }}, {times[i] + 0.1:.2f});')
    inner = (f'{f"<p id={chr(34)}{cid}-title{chr(34)} class={chr(34)}k-kicker{chr(34)}>{esc(title)}</p>" if title else ""}'
             f'<div id="{cid}-flow">{"".join(parts)}</div>')
    return _scene(cid, sc, style, inner, max(0.1, times[0] - 0.3), "wide", js)


def phrase(sc: Dict, c: Dict) -> str:
    """The line's own words, each appearing as the narrator says it."""
    cid = scene_id(sc["n"])
    words = str(c["words"]).split()
    accent = str(c.get("accent") or "").strip(".,;:!?").lower()
    kicker = str(c.get("kicker") or "")
    size = _fit(" ".join(words), [(14, 104), (22, 88), (34, 72), (48, 60), (99, 50)])
    t0 = _soon(when(sc, " ".join(words), 0.3), sc, 0.2)
    at = cinema.spoken_times(sc, words, t0, 0.18)
    style = f"""
#{cid}-line{{display:flex;flex-wrap:wrap;gap:0 {round(size * 0.24)}px}}
#{cid}-root .w{{display:block;font-family:var(--display);font-weight:800;font-size:{size}px;line-height:1.02;
  letter-spacing:-.035em;margin:0;color:var(--ink)}}
#{cid}-root .w.hi{{color:var(--accent)}}
"""
    spans, js = [], []
    for i, w in enumerate(words):
        hi = " hi" if accent and w.strip(".,;:!?").lower() == accent else ""
        spans.append(f'<p class="w{hi}" id="{cid}-w{i}">{esc(w)}</p>')
        js.append(f'  tl.fromTo("#{cid}-w{i}", {{ opacity: 0, filter: "blur(6px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.13 }}, {at[i]:.2f});')
    js.append(f'  tl.fromTo("#{cid}-rule", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: 0.5, ease: "power2.out" }}, {at[-1] + 0.2:.2f});')
    inner = (f'{f"<p id={chr(34)}{cid}-kick{chr(34)} class={chr(34)}k-kicker{chr(34)}>{esc(kicker)}</p>" if kicker else ""}'
             f'<div id="{cid}-line">{"".join(spans)}</div><div id="{cid}-rule" class="k-rule"></div>')
    return _scene(cid, sc, style, inner, max(0.1, at[0] - 0.35), "low", js, "max-width:900px")


def quote(sc: Dict, c: Dict) -> str:
    """Set as a poster; each word goes from faint to ink as it is said."""
    cid = scene_id(sc["n"])
    q, by = str(c["quote"]).strip('"“” '), str(c.get("by") or "")
    words = q.split()
    size = _fit(q, [(50, 50), (80, 42), (120, 36), (999, 30)])
    t0 = _soon(when(sc, q, 0.4), sc, 0.2)
    at = cinema.spoken_times(sc, words, t0, 0.2)
    style = f"""
#{cid}-mark{{font-family:var(--display);font-weight:800;font-size:150px;line-height:.55;color:var(--accent);margin:0;height:62px}}
#{cid}-q{{font-family:var(--display);font-weight:600;font-size:{size}px;line-height:1.2;letter-spacing:-.015em;margin:0}}
#{cid}-root .qw{{color:var(--ink)}}
"""
    spans = " ".join(f'<span class="qw" id="{cid}-q{i}">{esc(w)}</span>' for i, w in enumerate(words))
    js = [f'  tl.fromTo("#{cid}-q{i}", {{ opacity: 0.22 }}, {{ opacity: 1, duration: 0.12 }}, {at[i]:.2f});' for i in range(len(words))]
    js.insert(0, f'  tl.fromTo("#{cid}-mark", {{ scale: 0.6, opacity: 0, transformOrigin: "0 0" }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "back.out(1.6)" }}, {max(0.1, t0 - 0.1):.2f});')
    if by:
        js.append(f'  tl.fromTo("#{cid}-by", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, {at[-1] + 0.3:.2f});')
    inner = (f'<p id="{cid}-mark">&ldquo;</p><p id="{cid}-q">{spans}</p>'
             f'{f"<p id={chr(34)}{cid}-by{chr(34)} class={chr(34)}k-kicker{chr(34)}>{esc(by)}</p>" if by else ""}')
    return _scene(cid, sc, style, inner, max(0.1, t0 - 0.35), _side(sc), js, "width:700px")


def picture(sc: Dict, c: Dict) -> str:
    """The picture carries it: a small caption plate, low and out of the way."""
    cid = scene_id(sc["n"])
    label, kicker = str(c["label"]), str(c.get("kicker") or "")
    t0 = _soon(when(sc, label, 0.6), sc, 0.3)
    style = f"#{cid}-label{{font-family:var(--display);font-weight:800;font-size:{_fit(label, [(24, 44), (40, 36), (99, 30)])}px;line-height:1.08;letter-spacing:-.02em;margin:0;color:var(--ink)}}"
    inner = (f'{f"<p id={chr(34)}{cid}-kick{chr(34)} class={chr(34)}k-kicker{chr(34)}>{esc(kicker)}</p>" if kicker else ""}'
             f'<p id="{cid}-label">{esc(label)}</p>')
    return _scene(cid, sc, style, inner, t0, "low", [], "max-width:640px;padding:20px 28px")


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
