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


_STOP = {
    "about", "after", "again", "against", "already", "although", "always",
    "among", "another", "around", "because", "become", "becomes", "been",
    "before", "being", "below", "between", "both", "could", "does", "doing",
    "during", "each", "either", "enough", "every", "first", "from", "have",
    "having", "here", "however", "into", "itself", "just", "last", "like",
    "made", "make", "makes", "many", "more", "most", "much", "must", "never",
    "next", "not", "now", "often", "once", "only", "other", "over", "same",
    "several", "since", "some", "still", "such", "than", "that", "their",
    "them", "then", "there", "these", "they", "this", "those", "through",
    "today", "under", "until", "very", "what", "when", "where", "which",
    "while", "will", "with", "within", "without", "would", "year", "years",
}


def _content_words(text: str) -> set:
    import re

    return {
        w for w in re.findall(r"[a-z][a-z-]{3,}", (text or "").lower())
        if w not in _STOP
    }


def grounding(text: str, stories) -> float:
    """Share of the paragraph's distinctive words that appear in the material.

    The teaser prompt used to say 'name concrete things (a synthetic cell, a
    disc production line)'. The model read that as content rather than as an
    illustration and opened six of fourteen editions with a synthetic cell —
    including editions containing no such story. The prompt is fixed, but the
    failure is worth being able to detect rather than re-read prompts for: a
    paragraph about something that is not in the edition scores low here.
    """
    words = _content_words(text)
    if not words:
        return 1.0
    source = _content_words(
        " ".join(
            f"{s.title} {(s.brief or {}).get('thesis') or ''} "
            f"{(s.brief or {}).get('angle') or ''}"
            for s in stories
        )
    )
    return round(len(words & source) / len(words), 3)


# Calibrated against the eleven teasers already shipped.
#
# The whole-paragraph score alone is not enough: a leaked opening followed by
# three legitimate sentences about the edition still scores 0.46, because the
# rest of the paragraph really is on topic. The signal lives in the FIRST
# sentence, which is where the wrong subject lands and where a reader notices
# it — grounded openings scored 0.40-0.50, leaked ones 0.00-0.32.
MIN_GROUNDING = 0.30
MIN_OPENING_GROUNDING = 0.35


def _opening(text: str) -> str:
    import re

    return re.split(r"(?<=[.;—])\s", (text or "").strip())[0]


def teaser_problem(text: str, stories) -> Optional[str]:
    """Why this teaser should not ship, or None."""
    whole = grounding(text, stories)
    opening = grounding(_opening(text), stories)
    if opening < MIN_OPENING_GROUNDING:
        return f"opening only {opening:.0%} grounded in this edition"
    if whole < MIN_GROUNDING:
        return f"paragraph only {whole:.0%} grounded in this edition"
    return None


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
    story_lines = "\n".join(
        f"- {s.title}: {(s.brief.get('thesis') or '')[:220]}" for s in stories
    )
    teaser = _write("digest.teaser", stories=story_lines)

    # Retry when the paragraph is not about this edition. Cheaper than shipping
    # an opening that describes stories the reader will not find.
    problem = teaser_problem(teaser, stories) if teaser else None
    if problem:
        logger.warning(f"digest: teaser rejected — {problem}; retrying")
        retry = _write("digest.teaser", stories=story_lines)
        if retry and not teaser_problem(retry, stories):
            teaser = retry
        elif teaser_problem(teaser, stories):
            logger.warning(
                "digest: teaser still ungrounded, dropping it — better no "
                "opening than one about stories the edition does not contain"
            )
            teaser = None

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


def _narrative_material(story) -> str:
    """Everything about one story the essay writer may draw on.

    Deliberately richer than the per-section blocks: a narrative earns its
    length by making connections, and it can only connect what it can see.
    Commenter usernames are included because naming them is what makes the
    essay feel reported rather than summarised — and because an unnamed
    attribution is unverifiable.
    """
    b = story.brief or {}
    parts = [
        f'TITLE: "{story.title}"',
        f"thesis: {b.get('thesis') or '(none)'}",
        f"why now: {b.get('why_now') or '(none)'}",
        f"tension: {b.get('tension') or '(none)'}",
        f"stakes: {b.get('stakes') or '(none)'}",
        f"facts:\n{_facts_block(b, limit=6)}",
        f"numbers:\n{_numbers_block(b, limit=4)}",
        f"discussion (use these usernames verbatim):\n{_discussion_block(b, limit=5)}",
        f"researched sources:\n{_context_block(b)}",
        f"open questions (never resolve):\n{_unknowns_block(b, limit=4)}",
    ]
    return "\n".join(parts)


def compose_narrative(digest) -> List[Section]:
    """One essay across the whole edition, instead of discrete sections.

    Returns a single `deep` section so the renderers need no special case: to
    them it is one long piece with a title, which is exactly what it is.
    """
    if not digest.stories:
        return []

    material = "\n\n---\n\n".join(_narrative_material(s) for s in digest.stories)
    body = _write("digest.narrative", material=material[:22000])
    if not body:
        logger.warning("digest: narrative failed — no edition produced")
        return []

    # Sources from every story, so the essay's claims stay traceable even
    # though the prose itself names them inline.
    sources = []
    for s in digest.stories:
        sources.extend(s.brief.get("context_pages") or [])

    logger.info(f"digest: narrative composed ({len(body)} chars over {len(digest.stories)} stories)")
    return [Section(
        kind="deep",
        title=f"{digest.generated_at:%A}'s reading",
        body=body,
        sources=sources[:8],
    )]
