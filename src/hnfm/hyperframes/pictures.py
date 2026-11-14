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
from typing import Dict, List, Optional

from . import hermes

logger = logging.getLogger(__name__)

ASK = """You choose the picture behind one shot of a narrated news video.
Reply with one JSON object and nothing else:
{"picture": "<what the picture shows>"}

The picture:
- shows the thing this line is about: a concrete subject, where it is, what is happening;
- is 10 to 30 words, plain description, no camera or style words (the film's style is added for you);
- has no readable words, letters, numbers, signs, screens of text or logos in it;
- shows no real person's face up close (a figure from behind, hands, or objects instead);
- is not the same picture as any listed under "already".
"""

_STYLE_WORDS = re.compile(r"\b(photo(graph)?|render|4k|8k|style|cinematic|claymation|watercolou?r|"
                          r"illustration|aardman|highly detailed)\b", re.I)


def _key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def check(desc: str) -> List[str]:
    """Why a description is refused, if it is."""
    notes = []
    n = len(desc.split())
    if n < 8 or n > 36:
        notes.append(f"the picture must be 10 to 30 words; this is {n}")
    if re.search(r"\b(sign|text|words?|letters?|caption|headline|logo|label)s?\b.*\b(say|says|reads?|reading|that)\b",
                 desc, re.I):
        notes.append("no readable words in the picture")
    return notes


def describe(brief: Dict, sc: Dict, already: List[str]) -> Optional[str]:
    """One description for a beat, or None if the agent gives none that passes."""
    msg = {
        "story": brief["title"],
        "section": sc.get("section_text") or sc["text"],
        "this shot's line": sc["text"],
        "already": already[-6:] or ["nothing yet"],
    }
    message = "Choose the picture for this shot.\n\n```json\n" + json.dumps(msg, indent=1) + "\n```"
    session = f"hnfm-pic-{brief['item_id']}-{brief['run']}-{brief['seg']}-{sc['n']}"
    for _ in range(2):
        try:
            got = hermes.ask(message, instructions=ASK, session=session, timeout=120)
        except hermes.AgentError as e:
            logger.info(f"picture for scene {sc['n']}: {e}")
            return None
        m = re.search(r"\{.*\}", got["text"] or "", re.S)
        try:
            desc = str(json.loads(m.group(0)).get("picture") or "").strip() if m else ""
        except ValueError:
            desc = ""
        desc = _STYLE_WORDS.sub("", desc).strip(" ,.")
        notes = check(desc) if desc else ["reply with the JSON object"]
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
