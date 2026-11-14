"""The shot plan: what each beat of a story video looks like.

For every beat of narration Hermes (the `hnfm` profile, the local model)
picks a **form** from a menu (still, drift, pan, sequence, punch, split,
type, continue) and describes the picture the form needs. The menu it is
shown changes as the film goes: code takes away what was just used and
rations what tires quickly (a pan, a sequence, full-frame type). So the
model chooses freely, but from a menu that keeps the film varied. That is
the whole balance between formula and freedom:

    code owns   what forms exist, how often each may come, where words can go
    the model   which form fits this line, what the picture shows, what changes

Then the pictures are drawn on the image model (the 4090), each composed to
leave the part of the frame where words will sit empty. A `sequence` is a
picture and three edits of it, each changing one small thing.

`continue` merges a beat into the one before, so the model also decides how
many shots the film has.
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

from . import author, hermes
from .pictures import FRAMINGS, _key, _similar, avoid, check

logger = logging.getLogger(__name__)

FORMS = {
    "still": "one picture that does not move",
    "drift": "one picture, the camera slowly pushes in or pulls back",
    "pan": "the camera slides sideways across a wide picture (rare)",
    "sequence": "three or four frames of the same scene, one small thing changing each time",
    "punch": "a wide picture, then a hard cut into one detail of it",
    "split": "two pictures side by side, for two things set against each other",
    "type": "no picture: big words on a plain ground, for a turn or a punchline",
    "continue": "keep the previous shot on screen through this line",
}

# Where words go, and what the picture is asked to leave empty for them.
ZONES = {
    "left": "the left third of the frame",
    "right": "the right third of the frame",
    "low": "the lower third of the frame",
    "top": "the top third of the frame",
}
_ZONE_TURN = ["left", "right", "low", "right", "top", "left"]

MERGE_MAX = 10.0  # seconds: a shot held longer than this stops being a shot


def allowed(sc: Dict, history: List[Dict]) -> List[str]:
    """The forms this beat may take, given the shots before it."""
    recent = [h["form"] for h in history[-6:]]
    last = recent[-1] if recent else None
    first_in_section = sc.get("part", 1) == 1
    out = []
    for f in FORMS:
        if f == last and f != "drift":
            continue
        if f == "pan" and "pan" in recent[-5:]:
            continue
        if f == "sequence" and (sc["seconds"] < 3.0 or "sequence" in recent[-2:]):
            continue
        if f == "type" and (first_in_section or "type" in recent[-4:]):
            continue
        if f == "split" and ("split" in recent[-5:] or first_in_section):
            continue
        if f == "punch" and sc["seconds"] < 3.4:
            continue
        if f == "continue":
            prev = history[-1] if history else None
            if (first_in_section or not prev or prev["form"] in ("type", "continue")
                    or prev["seconds"] + sc["seconds"] > MERGE_MAX):
                continue
        out.append(f)
    # A section opens on its own drawn picture: no new picture, no split.
    return out


def _parse(text: str) -> Dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def _picture(d: Dict, n: int) -> str:
    parts = [str(d.get(k) or "").strip(" ,.") for k in ("subject", "doing", "where")]
    if not (parts[0] and parts[2]):
        return ""
    return f"{FRAMINGS[n % len(FRAMINGS)]} {parts[0]} {parts[1]}, {parts[2]}".replace("  ", " ")


def check_shot(d: Dict, sc: Dict, forms: List[str], already: List[str]) -> List[str]:
    form = d.get("form")
    if form not in forms:
        return [f"form must be one of: {', '.join(forms)}"]
    if form in ("type", "continue") or sc.get("part", 1) == 1:
        return []
    notes = []
    desc = _picture(d, sc["n"])
    if not desc:
        notes.append("give `subject`, `doing` and `where`")
    else:
        notes += check(desc)
        if max((_similar(desc, a) for a in already), default=0) > 0.4:
            notes.append("the picture is too close to one the film already has; pick a different subject from the line")
    if form == "sequence":
        ch = d.get("changes")
        if not (isinstance(ch, list) and 2 <= len(ch) <= 4 and all(isinstance(c, str) and 2 <= len(c.split()) <= 14 for c in ch)):
            notes.append("`changes` must be a list of three short changes, 3-12 words each")
    if form == "split":
        sec = d.get("second") if isinstance(d.get("second"), dict) else {}
        if not _picture(sec, sc["n"] + 1):
            notes.append("`second` must be {subject, doing, where} for the right-hand picture")
    return notes


def ask(brief: Dict, sc: Dict, nxt: Optional[Dict], forms: List[str], already: List[str], zone: str) -> Dict:
    """The shot for one beat. Falls back to a still of the section's picture."""
    msg = {
        "story": brief["title"] + ". " + (brief.get("summary") or "")[:400],
        "this line": sc["text"],
        "next line": nxt["text"] if nxt else "(the film ends)",
        "seconds": sc["seconds"],
        "forms you may use": {f: FORMS[f] for f in forms},
        "keep empty": ZONES[zone],
        "avoid": avoid(already) or ["nothing yet"],
    }
    if sc.get("part", 1) == 1:
        msg["note"] = "this line opens a section and already has its picture: choose only `form`"
    message = "Plan this shot.\n\n```json\n" + json.dumps(msg, indent=1) + "\n```"
    session = f"hnfm-shot-{brief['item_id']}-{brief['run']}-{sc['n']}-{int(time.time())}"
    for _ in range(3):
        try:
            got = hermes.ask(message, instructions=author.instructions("SHOTS.md"), session=session, timeout=120)
        except hermes.AgentError as e:
            logger.info(f"shot {sc['n']}: {e}")
            break
        d = _parse(got["text"])
        notes = check_shot(d, sc, forms, already)
        if not notes:
            d["asked"] = True
            return d
        message = "The shot was sent back: " + "; ".join(notes) + ". Reply with the JSON object again."
    return {"form": "still" if "still" in forms else forms[0], "asked": False}


def plan(brief: Dict, status=None) -> Dict:
    """Ask for every beat's shot, merge `continue`s, and set on each scene:
    form, zone, and what to draw (picture / sequence changes / second)."""
    scenes = brief["scenes"]
    history: List[Dict] = []
    already: List[str] = []
    out: List[Dict] = []
    for i, sc in enumerate(scenes):
        if status:
            status(f"planning shot {i + 1} of {len(scenes)}")
        forms = allowed(sc, history)
        zone = _ZONE_TURN[len(out) % len(_ZONE_TURN)]
        d = ask(brief, sc, scenes[i + 1] if i + 1 < len(scenes) else None, forms, already, zone)
        form = d.get("form", "still")
        if form == "continue" and out:
            _merge(out[-1], sc)
            history[-1]["seconds"] = out[-1]["seconds"]
            history.append({"form": "continue", "seconds": out[-1]["seconds"]})
            continue
        sc = dict(sc)
        sc.update(form=form, zone=zone, shot_asked=d.get("asked", False))
        if sc.get("part", 1) > 1 and form != "type":
            sc["draw"] = _picture(d, sc["n"])
            already.append(sc["draw"])
            if form == "sequence":
                sc["changes"] = [str(c) for c in d.get("changes", [])][:3]
            if form == "split":
                sc["draw2"] = _picture(d.get("second") or {}, sc["n"] + 1)
        elif form == "sequence":
            sc["changes"] = []  # a section's own frames are its sequence
        out.append(sc)
        history.append({"form": form, "seconds": sc["seconds"]})
    for k, sc in enumerate(out):
        sc["n"] = k + 1
    brief["scenes"] = out
    forms = [s["form"] for s in out]
    return {"shots": len(out), "beats": len(scenes), "forms": {f: forms.count(f) for f in sorted(set(forms))},
            "asked": sum(1 for s in out if s.get("shot_asked"))}


def _merge(a: Dict, b: Dict) -> None:
    """Hold shot `a` through beat `b`."""
    off = b["start"] - a["start"]
    a["text"] = a["text"] + " " + b["text"]
    a["cues"] = a["cues"] + b["cues"]
    a["words"] = (a.get("words") or []) + [{"w": w["w"], "t": round(w["t"] + off, 2)} for w in b.get("words") or []]
    a["seconds"] = round(b["start"] + b["seconds"] - a["start"], 2)
    a["held"] = a.get("held", 1) + 1


# ── Drawing ─────────────────────────────────────────────────────────────

def _compose(desc: str, zone: Optional[str], theme) -> str:
    from ..content.art_direction import compose_prompt

    room = (f", composed with the main subject away from {ZONES[zone]}, which is calm, open, uncluttered background"
            if zone else "")
    return compose_prompt(desc + room, theme)


def draw(brief: Dict, folder: str, status=None) -> Dict:
    """Draw what the plan asks for, reusing anything drawn before for the
    same words. Sets sc["picture"], sc["sequence"], sc["picture2"]."""
    from ..content.art_direction import format_dims, get_theme
    from ..video.image_generator import ImageGenerationService

    theme = get_theme(brief.get("theme"))
    w, h = format_dims("16:9")
    svc = ImageGenerationService()
    store = os.path.join(folder, "pictures")
    os.makedirs(store, exist_ok=True)
    made = reused = missed = 0

    def one(prompt: str, name: str, ref: Optional[str] = None) -> Optional[str]:
        nonlocal made, reused, missed
        path = os.path.join(store, name + ".png")
        if os.path.exists(path):
            reused += 1
            return path
        try:
            if ref:
                svc.generate_and_save_edit(prompt, ref, store, name + ".png", width=w, height=h)
            else:
                svc.generate_and_save_image(prompt, store, name + ".png", width=w, height=h)
            made += 1
            return path if os.path.exists(path) else None
        except Exception as e:
            logger.warning(f"picture not drawn ({name}): {e}")
            missed += 1
            return None

    todo = [s for s in brief["scenes"] if s.get("draw")]
    for i, sc in enumerate(todo):
        if status:
            status(f"drawing shot {i + 1} of {len(todo)} ({sc['form']})")
        zone = None if sc["form"] in ("split",) else sc["zone"]
        key = _key(brief["title"] + "|" + sc["draw"] + "|" + str(zone))
        base = one(_compose(sc["draw"], zone, theme), key)
        if not base:
            continue
        sc["picture"] = base
        if sc["form"] == "sequence" and sc.get("changes"):
            seq, ref = [base], base
            for j, change in enumerate(sc["changes"]):
                nxt = one(f"Same scene, same characters, same framing and style. Only this changes: {change}.",
                          f"{key}-e{j + 1}", ref)
                if not nxt:
                    break
                seq.append(nxt)
                ref = nxt
            sc["sequence"] = seq
        if sc["form"] == "split" and sc.get("draw2"):
            sc["picture2"] = one(_compose(sc["draw2"], None, theme), _key(brief["title"] + "|" + sc["draw2"]))
    return {"made": made, "reused": reused, "missed": missed, "wanted": len(todo)}
