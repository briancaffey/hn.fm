"""Turning a pile of briefs into an edition someone wants to read.

A ranked list of summaries is not a brief — it has no shape, and every item
arrives at the same volume. This module gives the day an arc:

    teaser      one paragraph that sets up the ideas
    quick hits  the smaller stories, covered fast
    deep dives  one or two stories explained properly, with mechanism
    bonus       the surprising leftovers

Roles are assigned by rank, not by the model: `select_stories` already orders
by the triage score, and letting a second model re-litigate that would put two
disagreeing judgements in series. The model's job here is writing, not ranking.

Every section is written from the Story Brief — never from raw article text —
so the brief's verification (quote checking, comment-id checking) is upstream
of everything a reader sees. A section that fails to generate is dropped, not
faked: a short edition is honest, a padded one is not.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# One or two features, never three: past two the edition stops being a brief
# and starts being homework for a 20-minute commute.
DEFAULT_DEEP_DIVES = 2


@dataclass
class Section:
    kind: str            # teaser | quick | deep | bonus
    title: str
    body: str
    story_id: Optional[int] = None
    url: Optional[str] = None
    hn_url: Optional[str] = None
    sources: List[dict] = field(default_factory=list)


def _facts_block(brief: dict, limit: int = 8) -> str:
    facts = [f for f in (brief.get("key_facts") or []) if f.get("claim")][:limit]
    if not facts:
        return "(none extracted)"
    return "\n".join(f"- {f['claim']}" for f in facts)


def _numbers_block(brief: dict, limit: int = 6) -> str:
    nums = [n for n in (brief.get("numbers") or []) if n.get("value")][:limit]
    if not nums:
        return "(none)"
    # Written form, not spoken: this is going on a page.
    return "\n".join(
        f"- {n['value']} — {n.get('context') or n.get('of') or ''}" for n in nums
    )


def _discussion_block(brief: dict, limit: int = 6) -> str:
    cis = (brief.get("comment_insights") or [])[:limit]
    if not cis:
        return "(no discussion insights were extracted)"
    return "\n".join(
        f"- [{c.get('kind')}] {c.get('author')}: {c.get('insight')}\n"
        f'  verbatim: "{(c.get("quote") or "")[:200]}"'
        for c in cis
    )


def _context_block(brief: dict) -> str:
    pages = brief.get("context_pages") or []
    if not pages:
        return "(none)"
    return "\n".join(f"- {p.get('title')} ({p.get('url')})" for p in pages)


def _unknowns_block(brief: dict, limit: int = 6) -> str:
    unknowns = (brief.get("unknowns") or [])[:limit]
    return "\n".join(f"- {u}" for u in unknowns) if unknowns else "(none listed)"


def _write(task: str, **fields) -> Optional[str]:
    """One prose section. Returns None on failure — callers drop, never fake."""
    from ..content.llm_service import LLMService
    from ..content.prompts import render

    try:
        text = LLMService(task=task).generate_content(render(task, **fields))
        return (text or "").strip() or None
    except Exception as e:
        logger.warning(f"digest: section {task} failed (dropped): {e}")
        return None


def compose(digest, deep_dives: int = None) -> List[Section]:
    """Build the edition's sections from a `Digest` of briefed stories."""
    stories = digest.stories
    if not stories:
        return []

    deep_dives = int(
        deep_dives if deep_dives is not None
        else os.getenv("DIGEST_DEEP_DIVES", DEFAULT_DEEP_DIVES)
    )
    # Highest-ranked stories earn the long treatment; the rest are quick hits.
    deep = stories[:deep_dives]
    quick = stories[deep_dives:]

    sections: List[Section] = []

    # Teaser last-to-first in importance but first on the page. Written from
    # theses only: it should set up the day, not preview each item.
    teaser = _write(
        "digest.teaser",
        stories="\n".join(
            f"- {s.title}: {(s.brief.get('thesis') or '')[:220]}" for s in stories
        ),
    )
    if teaser:
        sections.append(Section(kind="teaser", title="", body=teaser))

    for s in quick:
        body = _write(
            "digest.quickhit",
            title=s.title,
            thesis=s.brief.get("thesis") or "",
            why_now=s.brief.get("why_now") or "",
            tension=s.brief.get("tension") or "",
            facts=_facts_block(s.brief, limit=5),
            discussion=_discussion_block(s.brief, limit=3),
            unknowns=_unknowns_block(s.brief, limit=4),
        )
        if body:
            sections.append(Section(
                kind="quick", title=s.title, body=body,
                story_id=s.item_id, url=s.url, hn_url=s.hn_url,
            ))

    for s in deep:
        body = _write(
            "digest.deepdive",
            title=s.title,
            thesis=s.brief.get("thesis") or "",
            why_now=s.brief.get("why_now") or "",
            stakes=s.brief.get("stakes") or "",
            tension=s.brief.get("tension") or "",
            facts=_facts_block(s.brief),
            numbers=_numbers_block(s.brief),
            discussion=_discussion_block(s.brief),
            context=_context_block(s.brief),
            unknowns=_unknowns_block(s.brief),
        )
        if body:
            sections.append(Section(
                kind="deep", title=s.title, body=body,
                story_id=s.item_id, url=s.url, hn_url=s.hn_url,
                sources=s.brief.get("context_pages") or [],
            ))

    # Bonus draws on numbers, unknowns and discussion across the whole edition
    # — the leftovers that were interesting but had nowhere to sit.
    material = "\n\n".join(
        f"{s.title}\nnumbers:\n{_numbers_block(s.brief, 4)}\n"
        f"open questions:\n{_unknowns_block(s.brief, 3)}\n"
        f"discussion:\n{_discussion_block(s.brief, 3)}"
        for s in stories
    )
    bonus = _write("digest.bonus", material=material[:9000])
    if bonus:
        items = [ln.strip(" -•\t") for ln in bonus.splitlines() if ln.strip()]
        if items:
            sections.append(Section(
                kind="bonus", title="Also worth knowing",
                body="\n".join(items),
            ))

    logger.info(
        "digest: composed "
        + ", ".join(f"{k}={sum(1 for s in sections if s.kind == k)}"
                    for k in ("teaser", "quick", "deep", "bonus"))
    )
    return sections
