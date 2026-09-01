"""The Story Brief — the cheap text half's output artifact (plans/09).

One structured brief per run, consumed by the script room (plan 11) and the
art direction (plans 12/13). Before it, the script prompt received
`content_clean` + `summary` and the image prompt received `run_summary` + one
line; neither had the whole picture, and nothing carried what the source did
NOT say.

**Why two LLM calls rather than one.** The brief has two halves that are
different kinds of work:

  - *Framing* (thesis, angle, tension, unknowns) is editorial judgement. It
    wants a higher temperature — finding the angle is a creative act.
  - *Evidence* (facts, entities, numbers) is faithful extraction. It wants a
    low temperature and a hard rule that every claim carries a verbatim quote.

A single call cannot run at two temperatures, and asking one response to be
both imaginative and literal is asking it to do the thing it is worst at. The
split also degrades better: if extraction fails, the framing still stands, and
the brief is still usable. Smaller schemas adhere more reliably as a bonus,
not as the main reason.

Both halves are non-fatal. A run without a brief falls back to the pre-plans/09
inputs, which is worse but not broken.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

FRAMING_PROMPT = "brief.framing"
EVIDENCE_PROMPT = "brief.evidence"
COMMENTS_PROMPT = "brief.comments"

# Framing sees a trimmed article (the angle is visible early); extraction gets
# more, since a fact can appear anywhere.
_FRAMING_CHARS = 6000
_EVIDENCE_CHARS = 12000
# Words of consecutive overlap required to accept a non-verbatim quote. Eight is
# long enough that hitting one by chance is implausible, short enough to survive
# a model tidying punctuation mid-sentence.
_SHINGLE = 8


def build(
    title: str,
    summary: str,
    content_clean: str,
    signals: Optional[dict] = None,
    thread: Optional[list] = None,
    context_pages: Optional[list] = None,
) -> dict:
    """Assemble a Story Brief. Returns a dict shaped like `llm_schemas.StoryBrief`.

    Raises RuntimeError only if BOTH halves fail — a partial brief is worth
    more than none, and the caller records which half is missing.
    """
    from .llm_service import LLMService
    from .llm_schemas import StoryFraming, StoryEvidence, DiscussionEvidence
    from .prompts import render
    from . import scrape_signals as _sig
    from . import comments as _comments

    signal_line = (
        _sig.summarize(signals) if signals else "no retrieval report available"
    )

    framing, evidence, errors = None, None, []

    try:
        framing = LLMService(task=FRAMING_PROMPT).generate_structured(
            render(
                FRAMING_PROMPT,
                title=title or "(untitled)",
                summary=(summary or "")[:2000],
                content=(content_clean or "")[:_FRAMING_CHARS],
                signals=signal_line,
            ),
            StoryFraming,
        )
    except Exception as e:
        errors.append(f"framing: {e}")
        logger.warning(f"brief framing failed: {e}")

    try:
        evidence = LLMService(task=EVIDENCE_PROMPT).generate_structured(
            render(EVIDENCE_PROMPT, content=(content_clean or "")[:_EVIDENCE_CHARS]),
            StoryEvidence,
        )
    except Exception as e:
        errors.append(f"evidence: {e}")
        logger.warning(f"brief evidence failed: {e}")

    # The discussion is its own extraction rather than extra context on the
    # article call. A thin article with an expert thread is common on HN, and
    # merging them lets the article's emptiness suppress the thread's value.
    discussion = None
    if thread:
        try:
            discussion = LLMService(task=COMMENTS_PROMPT).generate_structured(
                render(
                    COMMENTS_PROMPT,
                    title=title or "(untitled)",
                    summary=(summary or "")[:1500],
                    comments=_comments.as_prompt_block(thread),
                ),
                DiscussionEvidence,
            )
        except Exception as e:
            errors.append(f"comments: {e}")
            logger.warning(f"brief comments failed: {e}")

    if framing is None and evidence is None:
        raise RuntimeError(f"story brief failed entirely — {'; '.join(errors)}")

    brief = {
        "thesis": "", "why_now": "", "stakes": "", "angle": "", "tension": "",
        "visual_affordances": [], "unknowns": [],
        "key_facts": [], "entities": [], "numbers": [],
        "comment_insights": [],
        "context_pages": [],
    }
    if framing:
        brief.update(framing.model_dump())
    if evidence:
        ev = evidence.model_dump()
        brief["key_facts"] = _verified_facts(ev["key_facts"], content_clean or "")
        brief["entities"] = ev["entities"]
        brief["numbers"] = ev["numbers"]
    if discussion:
        # Verified against the ids actually fetched: the model is shown real
        # comment ids, so an id that is not among them is fabrication, not a
        # near miss.
        brief["comment_insights"] = _comments.verify_comment_facts(
            [ci if isinstance(ci, dict) else ci.model_dump()
             for ci in discussion.comment_insights],
            thread or [],
        )
    if context_pages:
        # Recorded for provenance, so a reader can see which extra sources the
        # brief drew on and the renderer can cite them.
        brief["context_pages"] = [
            {"url": p.url, "title": p.title, "reason": p.reason}
            for p in context_pages
        ]
    if errors:
        brief["partial"] = errors
    return brief


def _normalize(text: str) -> str:
    """Whitespace- and quote-insensitive form, for quote checking."""
    import re

    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


def _verified_facts(facts: list, content: str) -> list:
    """Drop article-sourced facts whose quote isn't actually in the article.

    The prompt demands a verbatim quote; this checks it. A fabricated quote is
    the most dangerous output the pipeline can produce, because everything
    downstream treats `key_facts` as ground truth — the script writer is
    explicitly told it may rely on them. Cheap to verify, so verify.

    Comment-sourced facts are verified separately, against the comment tree —
    see content/comments.verify_comment_facts.

    Two-stage check. An exact substring match is the clean case. Failing that,
    an 8-word shingle from the quote must appear in the article: local models
    reliably identify the right sentence but often normalise it slightly while
    copying — a dropped article, an expanded contraction, a joined hyphenate —
    and exact matching alone rejected *every* fact on a story whose article
    plainly contained the material. A paraphrase invented from nothing shares
    no 8-word run with the source, so this still catches fabrication; it just
    stops punishing transcription drift.
    """
    haystack = _normalize(content)
    haystack_words = haystack.split()
    shingles = {
        " ".join(haystack_words[i:i + _SHINGLE])
        for i in range(max(0, len(haystack_words) - _SHINGLE + 1))
    }

    kept = []
    for fact in facts:
        if fact.get("source") == "comment":
            kept.append(fact)
            continue
        quote = _normalize(fact.get("quote") or "")
        if not quote:
            logger.info(f"brief: dropped unquoted fact — {str(fact.get('claim'))[:80]}")
            continue
        if quote in haystack:
            kept.append(fact)
            continue
        words = quote.split()
        if len(words) >= _SHINGLE and any(
            " ".join(words[i:i + _SHINGLE]) in shingles
            for i in range(len(words) - _SHINGLE + 1)
        ):
            # Grounded but not verbatim. Recorded on the fact so a consumer
            # that needs a literal quote can tell the difference.
            fact["quote_match"] = "partial"
            kept.append(fact)
            continue
        logger.info(
            f"brief: dropped fact with unverifiable quote — "
            f"{str(fact.get('claim'))[:80]}"
        )
    return kept
