"""Fact sheets: what the station knows about a story (issue #30).

A piece is not written from the research brief. The brief is an essay
("the story explores the tension between..."), and the local model reads
essays back out word for word. A fact sheet is the brief and the article
boiled down, once, at low temperature, to what a radio writer needs: what
the thing is, the hook, a few concrete facts, the catch, and what people
said about it as a caller would say it.

Made once per story and kept on disk, so a headline this hour and a
two-hander tonight are written from the same checked facts and the
extraction is paid for once.
"""

import json
import logging
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from . import radio_root

logger = logging.getLogger(__name__)

TASK = "radio.facts"
VERSION = 2  # bump to invalidate every cached sheet


class FactSheet(BaseModel):
    thin: bool = Field(default=False, description="True if the material is too thin to say what the thing is.")
    what: str = Field(description="One plain sentence: what it is or what happened.")
    hook: str = Field(description="The most concrete, surprising thing.")
    facts: List[str] = Field(description="Three to five short concrete facts.")
    catch: str = Field(default="", description="The main objection, limit or open question; empty if none.")
    callers: List[str] = Field(default_factory=list, description="Up to three points from the discussion, as a caller would say them.")


def _path(item_id: int) -> str:
    d = os.path.join(radio_root(), "sheets")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{item_id}.json")


def cached(item_id: int) -> Optional[dict]:
    try:
        with open(_path(item_id)) as f:
            data = json.load(f)
        return data if data.get("version") == VERSION else None
    except (OSError, ValueError):
        return None


def sheet_for(item_id: int) -> Optional[dict]:
    """{item_id, title, kind, score, comments, sheet: {...}} for a story,
    from the cache or one model call. None if there is nothing to read or
    the material is too thin to air."""
    hit = cached(item_id)
    if hit:
        return None if hit["sheet"].get("thin") else hit

    from ..content.llm_service import LLMService
    from ..content.prompts import render
    from ..db import repo
    from ..digest.compose import _punchline_material
    from ..digest.select import _scraped_material

    item = repo.get_item(item_id)
    if not item or not item.title:
        return None
    record = repo.get_latest_story_brief(item_id) or {}
    brief = record.get("brief") or {}
    summary, excerpt = _scraped_material(repo, item_id, record.get("run") or 1)
    excerpt = (excerpt or item.text or "").strip()
    if not brief.get("thesis") and not summary and len(excerpt) < 200:
        return None

    class _S:
        pass

    st = _S()
    st.title, st.url, st.brief, st.summary, st.excerpt = item.title, item.url, brief, summary, ""
    from .material import _anonymise

    standing = f"On Hacker News: {item.score or 0} points, {item.descendants or 0} comments."
    try:
        sheet = LLMService(task=TASK).generate_structured(render(
            TASK, title=item.title, standing=standing,
            material=_anonymise(_punchline_material(st)) if (brief.get("thesis") or summary) else "(no research brief)",
            excerpt=excerpt[:3500] or "(none)",
        ), FactSheet)
    except Exception as e:
        logger.warning(f"radio: fact sheet for {item_id} failed: {e}")
        return None
    out = {
        "version": VERSION, "item_id": item_id, "title": item.title, "kind": story_kind(item.title),
        "score": item.score or 0, "comments": item.descendants or 0, "sheet": sheet.model_dump(),
    }
    with open(_path(item_id), "w") as f:
        json.dump(out, f)
    return None if sheet.thin else out


def story_kind(title: str) -> str:
    t = (title or "").lower()
    if t.startswith("show hn"):
        return "show_hn"
    if t.startswith("ask hn"):
        return "ask_hn"
    return "story"


def render_story(s: dict, with_callers: bool = False, angle: Optional[str] = None) -> str:
    """A sheet as the writer sees it: plain statements, no labels worth
    reading out. ("The hook:" and "The catch:" were read out.)"""
    sh = s["sheet"]
    lines = [f'STORY: "{s["title"]}"', f"- {sh['what']}", f"- {sh['hook']}"]
    lines += [f"- {f}" for f in sh.get("facts") or []]
    if sh.get("catch"):
        lines.append(f"BUT: {sh['catch']}")
    if with_callers:
        lines.append("CALLERS (one point each, in these words or close to them):")
        lines += [f"- caller{n}: {c}" for n, c in enumerate((sh.get("callers") or [])[:3], 1)]
    elif sh.get("callers"):
        lines.append("PEOPLE SAID:")
        lines += [f"- {c}" for c in sh["callers"][:2]]
    return "\n".join(lines)
