"""Quick items on new stories: the radio's punchlines (plans/20).

The station's staple is not the deep-dive episode, it is thirty seconds on
a story that just landed: the headline, then the two or three things worth
knowing, in a host's voice, over a light bed. The bullets come from the
same prompt the Punchline digest uses, written from the Story Brief when
there is one and from the scrape otherwise, so a brief costs one small
model call and is cached on disk by story.
"""

import json
import logging
import os
import re
from typing import List, Optional

from . import radio_root

logger = logging.getLogger(__name__)

MAX_BULLETS = 3


def _cache_path(item_id: int) -> str:
    d = os.path.join(radio_root(), "briefs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{item_id}.json")


def candidates(limit: int = 24, hours: int = 48) -> List[dict]:
    """New stories worth a brief: recent, from /new, with a Story Brief or
    at least a scrape; newest first. [{item_id, title, url, age_hours}]"""
    from datetime import datetime

    from ..db import repo

    rows, _ = repo.list_triage(offset=0, limit=400, include_generated=True)
    out = []
    for r in rows:
        if r.get("source") != "new":
            continue
        if (r.get("verdict") or "") == "unsuitable":
            continue
        t = r.get("time")
        age_h = None
        if t:
            try:
                age_h = round((datetime.utcnow() - datetime.utcfromtimestamp(int(t))).total_seconds() / 3600, 1)
            except Exception:
                age_h = None
        if age_h is not None and age_h > hours:
            continue
        out.append({"item_id": r["item_id"], "run": r.get("run"), "title": r.get("title") or f"Story {r['item_id']}",
                    "url": r.get("url"), "age_hours": age_h, "interest": r.get("interest")})
    out.sort(key=lambda x: (x["age_hours"] if x["age_hours"] is not None else 1e9))
    return out[:limit]


def brief_for(item_id: int, run: Optional[int] = None) -> Optional[dict]:
    """{item_id, title, bullets: [...]} — cached; one model call the first time."""
    path = _cache_path(item_id)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass

    from ..db import repo
    from ..digest.compose import _punchline_material, parse_bullets, scrub_bullets
    from ..digest.select import _scraped_material
    from ..content.llm_service import LLMService
    from ..content.prompts import render

    item = repo.get_item(item_id)
    if not item:
        return None
    title = item.title or f"Story {item_id}"
    record = repo.get_latest_story_brief(item_id) or {}
    brief = record.get("brief") or {}
    run = run or record.get("run") or 1
    summary, excerpt = ("", "") if brief.get("thesis") else _scraped_material(repo, item_id, run)

    class _Story:
        pass

    st = _Story()
    st.title, st.url, st.brief, st.summary, st.excerpt = title, item.url, brief, summary, excerpt
    st.hn_url = f"https://news.ycombinator.com/item?id={item_id}"
    if not brief.get("thesis") and not (summary or excerpt):
        return None
    try:
        text = LLMService(task="digest.punchline").generate_content(render(
            "digest.punchline", title=title, url=item.url or st.hn_url,
            material=_punchline_material(st),
        ))
    except Exception as e:
        logger.warning(f"radio brief for {item_id} failed: {e}")
        return None
    authors = [c.get("author") for c in (brief.get("comment_insights") or [])]
    bullets = scrub_bullets(parse_bullets(text or ""), authors)[:MAX_BULLETS]
    if not bullets:
        return None
    out = {"item_id": item_id, "title": title, "bullets": bullets}
    with open(path, "w") as f:
        json.dump(out, f)
    return out


def spoken(b: dict) -> str:
    """What the host reads: the headline as a sentence, then the bullets,
    with the punctuation a voice model needs to pause on."""
    title = re.sub(r"\s+", " ", b["title"]).strip().rstrip(".")
    parts = [f"{title}."]
    for bl in b["bullets"]:
        bl = bl.strip()
        if bl and bl[-1] not in ".!?":
            bl += "."
        parts.append(bl)
    return " ".join(parts)
