"""Getting a scene written, checked and accepted.

The author is Hermes. For each scene it is sent a small brief and returns
one HTML file. That file is read by rules here before the renderer ever
sees it, then mounted on its own and reviewed by the renderer (does it
run, does anything fall outside the frame, can the text be read). What
the review finds goes back to the author, twice at most. A scene that is
still wrong keeps the plain version the kit wrote, so a video always
comes out whole.
"""

import json
import logging
import os
import re
import shutil
import time
from typing import Dict, List, Optional, Tuple

from . import hermes, kit, render_client, scenes

logger = logging.getLogger(__name__)

ROUNDS = 3
MAX_BYTES = 24_000

_BLOCK = re.compile(r"```([a-zA-Z]*)[ \t]*\n(.*?)```", re.S)
_BANNED = [
    (re.compile(r"https?://", re.I), "it names a web address; nothing may be loaded from the network"),
    (re.compile(r"<link\b|@import", re.I), "it links a stylesheet; write styles in the one <style> block"),
    (re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|importScripts|eval|Function)\s*\("),
     "it calls something other than the timeline (fetch, eval and the like are not allowed)"),
    (re.compile(r"\b(setTimeout|setInterval|requestAnimationFrame)\s*\("), "it keeps its own clock; the timeline is the only clock"),
    (re.compile(r"Math\.random|Date\.now|new Date"), "it uses a random number or the date; a scene must render the same every time"),
    (re.compile(r"repeat\s*:\s*-1"), "it repeats forever (repeat: -1); give a finite count"),
    (re.compile(r"<br\s*/?>", re.I), "it uses <br>; separate lines are separate elements"),
    (re.compile(r"autoAlpha|visibility\s*:|display\s*:\s*[\"']"), "it animates visibility or display; fade with opacity"),
    (re.compile(r"\b(document\.cookie|localStorage|sessionStorage|window\.parent|window\.top|location\.)"),
     "it reaches outside the scene"),
    (re.compile(r"<(iframe|object|embed|video|audio|form|input)\b", re.I), "it embeds something a scene may not hold"),
]
_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)")
_SRC = re.compile(r"\bsrc\s*=\s*['\"]([^'\"]+)")

SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill")


def instructions(page: str = "SKILL.md") -> str:
    """The hnfm-video skill, sent with every request. The agent's profile
    has no tools, not even the one that reads skills (given it, the model
    spends its turns trying to save its answer as a new skill), so the
    page it works from travels with the brief. The same file is installed
    in Hermes for anyone using the skill by hand."""
    with open(os.path.join(SKILL_DIR, page)) as f:
        text = f.read()
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def scene_brief(brief: Dict, sc: Dict, before: str) -> Dict:
    cid = kit.scene_id(sc["n"])
    return {
        "id": cid,
        "seconds": sc["seconds"],
        "beat": (sc.get("beat") or "").replace("_", " "),
        "text": sc["text"],
        "cues": [{"t": round(c["t"] - sc["start"], 2), "text": c["text"]} for c in sc["cues"]],
        "image": sc.get("asset"),
        "story": {"title": brief["title"], "summary": (brief.get("summary") or "")[:300]},
        "before": before or "nothing yet: this is the first scene",
        "canvas": {"width": kit.WIDTH, "height": kit.HEIGHT},
        "safe": kit.SAFE,
    }


def extract(reply: str) -> Optional[Dict[str, str]]:
    """The scene's three parts out of the reply: {css, html, js}. The
    wrapper (template, root, timeline, registration) is written by the
    kit, because left to write it the author gets it nearly right."""
    parts = {"css": "", "html": "", "js": ""}
    for lang, body in _BLOCK.findall(reply or ""):
        lang = {"javascript": "js", "": "html"}.get(lang.lower(), lang.lower())
        if lang in parts and not parts[lang]:
            parts[lang] = body.strip()
    if not parts["html"]:
        return None
    # A whole file where only the inside was asked for: take the inside.
    m = re.search(r"<template[^>]*>(.*)</template>", parts["html"], re.S)
    if m:
        inner = m.group(1)
        style = re.search(r"<style[^>]*>(.*?)</style>", inner, re.S)
        script = re.search(r"<script[^>]*>(.*?)</script>", inner, re.S)
        parts["css"] = parts["css"] or (style.group(1).strip() if style else "")
        parts["js"] = parts["js"] or (script.group(1).strip() if script else "")
        inner = re.sub(r"<style[^>]*>.*?</style>|<script[^>]*>.*?</script>", "", inner, flags=re.S).strip()
        root = re.match(r"<div[^>]*data-composition-id[^>]*>(.*)</div>\s*$", inner, re.S)
        parts["html"] = (root.group(1) if root else inner).strip()
    # The timeline exists already; lines that make or register one are dropped.
    parts["js"] = "\n".join(
        line for line in parts["js"].splitlines()
        if not re.search(r"gsap\.timeline\(|window\.__timelines|^\s*\(function|^\s*\}\)\(\);?\s*$", line))
    return parts


def assemble(cid: str, parts: Dict[str, str]) -> str:
    js = "\n".join("  " + line for line in parts["js"].splitlines() if line.strip())
    return kit.wrap(cid, "\n" + parts["css"] + "\n", parts["html"], js)


def vet(parts: Dict[str, str], cid: str, image: Optional[str]) -> List[str]:
    """What the rules object to, in words the author can act on."""
    text = "\n".join(parts.values())
    notes = []
    if len(text.encode()) > MAX_BYTES:
        notes.append(f"the scene is {len(text.encode()) // 1000} KB; keep it under {MAX_BYTES // 1000} KB")
    if not parts["js"].strip():
        notes.append("the js block is empty: nothing moves. Add tl.fromTo(...) lines")
    if re.search(r"<(script|style|template|html|body|head)\b", parts["html"], re.I):
        notes.append("the html block must hold only the elements to show: no <script>, <style> or <template>")
    for pattern, why in _BANNED:
        if pattern.search(text):
            notes.append(why)
    for ref in _URL.findall(text) + _SRC.findall(text):
        if ref.strip() != (image or ""):
            notes.append(f"it refers to {ref.strip()[:60]!r}; the only file a scene may use is the image it was given"
                         + ("" if image else " (this scene has none)"))
    ids = set(re.findall(r'\bid="([^"]+)"', parts["html"]))
    stray = sorted(i for i in ids if not i.startswith(cid + "-"))
    if stray:
        notes.append(f"every id must start with {cid}- (rename: {', '.join(stray[:4])})")
    used = set(re.findall(r"#([A-Za-z][\w-]*)", parts["js"] + parts["css"]))
    missing = sorted(u for u in used if u.startswith(cid) and u not in ids and u != f"{cid}-root")
    if missing:
        notes.append(f"these ids are styled or animated but are not in the html: {', '.join(missing[:5])}")
    if re.search(r"\btl\.(from|to)\(", parts["js"]):
        notes.append("animate with tl.fromTo(...), not tl.from() or tl.to()")
    return list(dict.fromkeys(notes))


# What the renderer's review can find that makes a scene unusable, and what
# is worth passing back once but not worth losing the scene over.
_IGNORE = {"line_unread", "timeline_track_too_dense", "first_frame_empty", "container_overflow"}


def review(project: str, n: int, work: str) -> Tuple[List[str], List[str]]:
    """Mount the scene on its own and let the renderer look at it.
    Returns (errors, warnings) as sentences."""
    shutil.rmtree(work, ignore_errors=True)
    kit.single(project, n, work)
    got = render_client.check(work)
    if not got.get("ok"):
        return [f"the renderer could not load the scene: {str(got.get('error'))[:200]}"], []
    errors, warnings = [], []
    for part, section in (got.get("report") or {}).items():
        if not isinstance(section, dict):
            continue
        for f in section.get("findings") or []:
            code = f.get("code") or ""
            if code in _IGNORE or "index.html" in (f.get("sourceFile") or ""):
                continue
            where = f" (at {f['time']:.1f}s)" if isinstance(f.get("time"), (int, float)) else ""
            sel = f" [{f['selector']}]" if f.get("selector") and "composition" not in str(f.get("selector")) else ""
            line = f"{part}/{code}{sel}{where}: {(f.get('message') or '').strip()[:260]}"
            # A label a shade under the AA line is not worth losing a scene
            # over; text that cannot be read is.
            ratio = re.search(r"Contrast is ([\d.]+):1", f.get("message") or "")
            soft = bool(ratio) and float(ratio.group(1)) >= 3.0
            (errors if f.get("severity") == "error" and not soft else warnings).append(line)
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def describe(text: str) -> str:
    """Two or three words on what a scene shows, from its markup: enough
    to tell the next scene not to do the same again."""
    kinds = []
    if "k-stat" in text:
        kinds.append("a big figure")
    if "<svg" in text:
        kinds.append("a diagram")
    if "k-img" in text or "<img" in text:
        kinds.append("a full-frame picture")
    if text.count("<li") >= 2 or len(re.findall(r'class="[^"]*item', text)) >= 2:
        kinds.append("a list")
    if re.search(r"col|versus|compare|\bvs\b", text, re.I):
        kinds.append("a comparison")
    if not kinds:
        kinds.append("a headline phrase")
    return " and ".join(kinds[:2])


def write_scene(project: str, brief: Dict, sc: Dict, before: str, job: str = "") -> Dict:
    """One scene, start to finish. Returns a record of what happened; the
    project holds either the author's scene or the plain one."""
    n, cid = sc["n"], kit.scene_id(sc["n"])
    kit.keep_plain(project, n)
    record = {"scene": cid, "rounds": [], "accepted": False, "seconds": 0.0, "tokens": 0}
    session = f"hnfm-{job or 'job'}-{cid}-{int(time.time())}"
    message = ("Write this scene.\n\n```json\n" + json.dumps(scene_brief(brief, sc, before), indent=1) + "\n```")
    work = os.path.join(project, "work", cid)
    started = time.time()
    for round_no in range(1, ROUNDS + 1):
        entry = {"round": round_no}
        try:
            got = hermes.ask(message, instructions=instructions("FREEFORM.md"), session=session)
        except hermes.AgentError as e:
            entry["problem"] = str(e)
            record["rounds"].append(entry)
            break
        record["tokens"] += got["tokens"]
        entry["seconds"] = got["seconds"]
        entry["run_id"] = got.get("run_id")  # the Hermes run, for tracing a scene back
        parts = extract(got["text"])
        if not parts:
            notes = ["the reply held no html block"]
        else:
            notes = vet(parts, cid, sc.get("asset"))
        warnings = []
        text = assemble(cid, parts) if parts else ""
        if parts and not notes:
            kit.write_scene(project, n, text)
            notes, warnings = review(project, n, work)
        entry["findings"] = notes
        entry["warnings"] = warnings
        record["rounds"].append(entry)
        if not notes:
            # One chance to tidy what the review only warned about; if the
            # tidy breaks something the accepted version is kept.
            record["accepted"] = True
            record["looks_like"] = describe(text)
            _keep(project, n, "accepted")
            if not warnings or round_no >= ROUNDS - 1 or entry.get("tidy"):
                break
            message = _findings_message(warnings, "These are not errors, but fix them if you can")
            continue
        if record["accepted"]:
            break
        message = _findings_message(notes, "The scene was checked and these things are wrong")
    if record["accepted"]:
        _restore(project, n, "accepted")
    else:
        kit.restore_plain(project, n)
    shutil.rmtree(work, ignore_errors=True)
    record["seconds"] = round(time.time() - started, 1)
    return record


def _findings_message(lines: List[str], lead: str) -> str:
    return (f"{lead}:\n\n" + "\n".join(f"- {x}" for x in lines[:8])
            + "\n\nReturn all three blocks again, corrected.")


def _keep(project: str, n: int, tag: str) -> None:
    dst = os.path.join(project, tag, f"{kit.scene_id(n)}.html")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(os.path.join(project, kit.scene_file(n)), dst)


def _restore(project: str, n: int, tag: str) -> None:
    src = os.path.join(project, tag, f"{kit.scene_id(n)}.html")
    if os.path.exists(src):
        shutil.copy(src, os.path.join(project, kit.scene_file(n)))


# ── The storyboard: the author chooses a treatment and supplies its words ──

_JSON = re.compile(r"```(?:json)?\s*\n(.*?)```", re.S)
_DIGITS = re.compile(r"\d+(?:[.,]\d+)*")
_STOPWORDS = set("a an and are as at be but by for from has have if in into is it its of on or than that the their "
                 "then this to was were which while will with you your vs versus per more less most".split())


def card_brief(brief: Dict, sc: Dict, before: List[str]) -> Dict:
    return {
        "text": sc["text"],
        "cues": [{"t": round(c["t"] - sc["start"], 2), "text": c["text"]} for c in sc["cues"]],
        "beat": (sc.get("beat") or "").replace("_", " "),
        "seconds": sc["seconds"],
        "has_image": bool(sc.get("asset")),
        "story": {"title": brief["title"], "summary": (brief.get("summary") or "")[:300]},
        "before": before[-4:] or ["nothing yet: this is the first scene"],
        "numbers_said": sorted({d for d in _DIGITS.findall(sc["text"])}) or "none: do not put a number on screen",
    }


def parse_card(reply: str) -> Optional[Dict]:
    m = _JSON.findall(reply or "")
    text = m[-1] if m else (reply or "")
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < 0:
        return None
    try:
        card = json.loads(text[a:b + 1])
    except ValueError:
        return None
    return card if isinstance(card, dict) else None


def _strings(card: Dict) -> List[str]:
    """Everything in a card that would be shown."""
    out = []

    def walk(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(str(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk({k: v for k, v in card.items() if k not in ("treatment", "why")})
    return out


def _norm_number(s: str) -> str:
    s = s.replace(",", "")
    return s.rstrip("0").rstrip(".") if "." in s else s


def check_card(card: Dict, sc: Dict, brief: Dict, previous: Optional[str] = None) -> List[str]:
    """What is wrong with a card, in words the author can act on."""
    name = card.get("treatment")
    spec = scenes.TREATMENTS.get(name)
    if not spec:
        return [f"treatment must be one of: {', '.join(scenes.TREATMENTS)}"]
    if name == "picture" and not sc.get("asset"):
        return ["this scene has no image, so picture cannot be used; choose another treatment"]
    notes = []
    for f in spec["need"]:
        if card.get(f) in (None, "", [], {}):
            notes.append(f"{name} needs the field `{f}`")
    extra = [k for k in card if k not in spec["fields"] and k not in ("treatment", "why")]
    if extra:
        notes.append(f"{name} does not take: {', '.join(extra)}")
        for k in extra:
            card.pop(k, None)
    if notes:
        return notes

    for f, cap in spec["words"].items():
        if isinstance(card.get(f), str) and len(card[f].split()) > cap:
            notes.append(f"`{f}` is {len(card[f].split())} words; keep it to {cap}")
    if name == "compare":
        for side in ("left", "right"):
            d = card[side]
            if not (isinstance(d, dict) and d.get("name") and d.get("value") not in (None, "")):
                notes.append(f"`{side}` must be an object with `name` and `value`")
            elif len(str(d["name"]).split()) > 4 or len(str(d["value"]).split()) > 4:
                notes.append(f"`{side}`: name and value are each at most four words")
    if name == "bars":
        rows = card["rows"]
        if not (isinstance(rows, list) and 2 <= len(rows) <= 4 and all(
                isinstance(r, dict) and r.get("name") and scenes._num(r.get("value")) is not None for r in rows)):
            notes.append("`rows` must be two to four objects, each with `name` and a numeric `value`")
    if name in ("list", "steps"):
        items = card["items"]
        cap = 5 if name == "list" else 3
        if not (isinstance(items, list) and 2 <= len(items) <= 4 and all(isinstance(i, str) and i.strip() for i in items)):
            notes.append("`items` must be two to four short strings")
        elif any(len(i.split()) > cap + 1 for i in items):
            notes.append(f"each item is at most {cap} words")
    if notes:
        return notes

    shown = _strings(card)
    said = sc["text"] + " " + brief.get("title", "")
    if name == "figure" and not _DIGITS.search(str(card["value"])):
        notes.append("a figure's `value` must be a number from the narration; for words use `phrase`")
    # Numbers must be said in this line: the title's year is not a figure.
    have = {_norm_number(d) for d in _DIGITS.findall(sc["text"])}
    made_up = sorted({d for s in shown for d in _DIGITS.findall(s) if _norm_number(d) not in have})
    if made_up:
        notes.append(f"these numbers are not in the narration: {', '.join(made_up)}. Use only numbers the narrator says"
                     + (f" ({', '.join(sorted(have))})" if have else " (this line has none, so choose a treatment without numbers)"))
    ground = set(scenes._words(said + " " + (brief.get("summary") or "")))
    stems = {w[:5] for w in ground}
    words = [w for s in shown for w in scenes._words(s) if w not in _STOPWORDS and len(w) > 3 and not w[0].isdigit()]
    stray = sorted({w for w in words if w not in ground and w[:5] not in stems})
    if words and len(stray) > max(1, len(set(words)) // 3):
        notes.append(f"these words are not in the narration: {', '.join(stray[:6])}. Take the words on screen from `text`")
    if any(s.strip().endswith(".") and len(s.split()) > 6 for s in shown):
        notes.append("no sentences on screen: use fragments with no full stop")
    if name == "phrase":
        said_words = scenes._words(sc["text"])
        want = scenes._words(str(card["words"]))
        run = any(said_words[i:i + len(want)] == want for i in range(len(said_words) - len(want) + 1))
        if not run:
            notes.append("`words` must be a run of consecutive words copied from `text`, not a rearrangement")
        elif want and want[-1] in _STOPWORDS:
            notes.append(f"`words` ends on {want[-1]!r}; end the phrase on the word that carries it")
        elif len(want) < 3:
            notes.append("`words` needs at least three words")
        if card.get("accent") and len(str(card["accent"]).split()) != 1:
            card["accent"] = str(card["accent"]).split()[-1]
    for extra_field in ("kicker", "title"):
        v = str(card.get(extra_field) or "").strip().lower()
        if v and any(v == str(x).strip().lower() for k, x in card.items() if k not in (extra_field, "why", "treatment") and isinstance(x, str)):
            card.pop(extra_field)
    if previous and name == previous:
        notes.append(f"the previous scene was also a {name}; choose a different treatment")
    return notes


def direct_scene(project: str, brief: Dict, sc: Dict, before: List[str], previous: Optional[str] = None,
                 job: str = "") -> Dict:
    """One scene by storyboard: ask for a card, check it, build it, let
    the renderer review it. The plain scene stays if no card passes."""
    n, cid = sc["n"], kit.scene_id(sc["n"])
    kit.keep_plain(project, n)
    record = {"scene": cid, "rounds": [], "accepted": False, "seconds": 0.0, "tokens": 0}
    session = f"hnfm-{job or 'job'}-{cid}-{int(time.time())}"
    ask = card_brief(brief, sc, before)
    ask["treatments"] = scenes.menu(bool(sc.get("asset"))).splitlines()
    message = "Direct this scene.\n\n```json\n" + json.dumps(ask, indent=1) + "\n```"
    work = os.path.join(project, "work", cid)
    started = time.time()
    for round_no in range(1, ROUNDS + 1):
        entry = {"round": round_no}
        try:
            got = hermes.ask(message, instructions=instructions(), session=session)
        except hermes.AgentError as e:
            entry["problem"] = str(e)
            record["rounds"].append(entry)
            break
        record["tokens"] += got["tokens"]
        entry["seconds"] = got["seconds"]
        entry["run_id"] = got.get("run_id")  # the Hermes run, for tracing a scene back
        card = parse_card(got["text"])
        # Variety is asked for once; a second card of the same kind is
        # better than no card.
        notes = (["the reply held no JSON card"] if not card
                 else check_card(card, sc, brief, previous if round_no == 1 else None))
        if card and not notes:
            try:
                kit.write_scene(project, n, scenes.build(sc, card))
                errors, _warnings = review(project, n, work)
                notes = [f"on screen: {e}" for e in errors]
            except Exception as e:
                notes = [f"the card could not be laid out: {str(e)[:120]}"]
        entry["card"] = card
        entry["findings"] = notes
        record["rounds"].append(entry)
        if not notes:
            record.update(accepted=True, card=card, treatment=card["treatment"],
                          looks_like=_say(card))
            break
        message = _findings_message(notes, "The card was checked and these things are wrong").replace(
            "Return all three blocks again, corrected.", "Return the whole card again, corrected, in one json block.")
        if round_no == ROUNDS - 1:
            message += (" If the line does not hold what this treatment needs, use `phrase` instead: "
                        "three to seven words taken from `text`.")
    if not record["accepted"]:
        kit.restore_plain(project, n)
    shutil.rmtree(work, ignore_errors=True)
    record["seconds"] = round(time.time() - started, 1)
    return record


def _say(card: Dict) -> str:
    """A card in a few words, for the next scene's `before`."""
    t = card["treatment"]
    lead = next((s for s in _strings(card) if s), "")
    return f"a {t} ({lead[:40]})"
