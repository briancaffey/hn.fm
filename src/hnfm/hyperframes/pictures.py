"""A picture for each beat, described by Hermes and drawn by FLUX.

A narrated section already has one picture and a few edits of it. Cut into
beats of a few seconds, that is not enough: the same diorama for fifteen
seconds is the slide-deck look again. So every beat after a section's first
gets a picture of its own, tied to what is said in it.

Hermes (the `hnfm` profile, the local model) is asked what the picture
shows: a subject, a setting, an action, in its own words, never style words
(the story's art direction supplies those, so every picture belongs to the
same film). The image model on the 4090 draws it. Both run on the home lab.

A described picture is kept by the beat's words: making the video again
reuses it instead of drawing it again.
"""

import hashlib
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

from . import hermes

logger = logging.getLogger(__name__)

ASK = """You choose the picture behind one shot of a narrated news video, from what THIS line says.
Reply with one JSON object and nothing else:
{"subject": "<who or what the line is about, 2-8 words>",
 "doing": "<what is happening to or with it, 2-10 words>",
 "where": "<the place and era, 2-8 words, consistent with the story>"}

Rules:
- take the subject from the line itself: its person (as a figure), object, machine, document or place;
- a person is shown as a figure, never a face close up;
- no readable words, letters, numbers, signs or screens of text;
- no style or camera words (they are added for you);
- do not use a subject listed under "avoid".
"""

# Each shot gets the next framing in turn, so a film does not become one
# picture redrawn: the local model, shown earlier pictures, copied them.
FRAMINGS = [
    "a wide shot of",
    "a close-up of",
    "seen from behind,",
    "an overhead view of",
    "a low-angle shot of",
    "a medium shot of",
]

_COMMON = set("a an the of on in at with and under over from into onto its it is are to by for near beside "
              "placed sits sitting stands standing showing filled full soft light casting".split())


def _nouns(desc: str) -> List[str]:
    return [w for w in re.findall(r"[a-z]+", desc.lower()) if len(w) > 3 and w not in _COMMON]


def _similar(a: str, b: str) -> float:
    x, y = set(_nouns(a)), set(_nouns(b))
    return len(x & y) / max(1, len(x | y))

_STYLE_WORDS = re.compile(r"\b(photo(graph)?|render|4k|8k|style|cinematic|claymation|watercolou?r|"
                          r"illustration|aardman|highly detailed)\b", re.I)


VERSION = "2"


def _key(text: str) -> str:
    return hashlib.sha1((VERSION + "|" + text).encode()).hexdigest()[:12]


def check(desc: str) -> List[str]:
    """Why a description is refused, if it is."""
    notes = []
    n = len(desc.split())
    if n < 8 or n > 36:
        notes.append(f"subject, doing and where together must be 8 to 30 words; this is {n}")
    if re.search(r"\b(sign|text|words?|letters?|caption|headline|logo|label)s?\b.*\b(say|says|reads?|reading|that)\b",
                 desc, re.I):
        notes.append("no readable words in the picture")
    return notes


def avoid(already: List[str]) -> List[str]:
    """The subjects the film has leaned on: any word used in two or more
    earlier pictures."""
    seen: Dict[str, int] = {}
    for d in already:
        for w in set(_nouns(d)):
            seen[w] = seen.get(w, 0) + 1
    return sorted(w for w, n in seen.items() if n >= 2)[:14]


def describe(brief: Dict, sc: Dict, already: List[str]) -> Optional[str]:
    """One description for a beat, or None if the agent gives none that passes."""
    msg = {
        "story": brief["title"] + ". " + (brief.get("summary") or "")[:400],
        "this shot's line": sc["text"],
        "avoid": avoid(already) or ["nothing yet"],
    }
    message = "Choose the picture for this shot.\n\n```json\n" + json.dumps(msg, indent=1) + "\n```"
    # A fresh session each time: an old session's replies teach the old format.
    session = f"hnfm-pic-{brief['item_id']}-{brief['run']}-{brief['seg']}-{sc['n']}-{int(time.time())}"
    for _ in range(3):
        try:
            got = hermes.ask(message, instructions=ASK, session=session, timeout=120)
        except hermes.AgentError as e:
            logger.info(f"picture for scene {sc['n']}: {e}")
            return None
        m = re.search(r"\{.*\}", got["text"] or "", re.S)
        try:
            card = json.loads(m.group(0)) if m else {}
            parts = [str(card.get(k) or "").strip(" ,.") for k in ("subject", "doing", "where")]
            desc = (f'{FRAMINGS[sc["n"] % len(FRAMINGS)]} {parts[0]} {parts[1]}, {parts[2]}'
                    if parts[0] and parts[2] else "")
        except (ValueError, AttributeError):
            desc = ""
        desc = re.sub(r"\s{2,}", " ", _STYLE_WORDS.sub("", desc)).strip(" ,.")
        notes = check(desc) if desc else ["reply with the JSON object"]
        near = max((_similar(desc, d) for d in already), default=0)
        if desc and near > 0.4:
            notes.append("it is too close to a picture the film already has; choose a different subject from the line")
        if not notes:
            return desc
        message = "The picture was refused: " + "; ".join(notes) + ". Reply with the JSON object again."
    return None


def draw(prompt: str, out_png: str) -> bool:
    try:
        from ..content.art_direction import format_dims
        from ..video.image_generator import ImageGenerationService

        w, h = format_dims("16:9")
        ImageGenerationService().generate_and_save_image(
            prompt, os.path.dirname(out_png), os.path.basename(out_png), width=w, height=h)
        return os.path.exists(out_png)
    except Exception as e:
        logger.warning(f"picture not drawn: {e}")
        return False


def make(brief: Dict, folder: str, status=None) -> Dict:
    """Describe and draw a picture for every beat that is not a section's
    first. Sets sc["picture"] (a path) and sc["picture_said"]; returns a
    record for the status file."""
    from ..content.art_direction import compose_prompt, get_theme

    theme = get_theme(brief.get("theme"))
    store = os.path.join(folder, "pictures")
    os.makedirs(store, exist_ok=True)
    index_path = os.path.join(store, "index.json")
    try:
        index = json.load(open(index_path))
    except (OSError, ValueError):
        index = {}
    already, made, reused, missed = [], 0, 0, 0
    todo = [sc for sc in brief["scenes"] if sc.get("part", 1) > 1]
    for i, sc in enumerate(todo):
        if status:
            status(f"picture {i + 1} of {len(todo)}")
        key = _key(brief["title"] + "|" + sc["text"])
        rec = index.get(key)
        png = os.path.join(store, f"{key}.png")
        if rec and os.path.exists(png):
            sc["picture"], sc["picture_said"] = png, rec["said"]
            already.append(rec["said"])
            reused += 1
            continue
        said = describe(brief, sc, already)
        if not said:
            missed += 1
            continue
        if draw(compose_prompt(said, theme), png):
            sc["picture"], sc["picture_said"] = png, said
            index[key] = {"said": said, "scene": sc["n"]}
            already.append(said)
            made += 1
            with open(index_path, "w") as f:
                json.dump(index, f, indent=1)
        else:
            missed += 1
    return {"made": made, "reused": reused, "missed": missed, "wanted": len(todo)}
