"""Deterministic quality signals about what the scraper actually retrieved.

`producibility` (plans/09) asks "given what we retrieved, can we build a good
video?" — a question that is mostly answerable by *looking at the text*, with
no LLM involved. Counting paragraphs is cheaper, faster and more reliable than
asking a model to estimate how well a page scraped.

This exists because `triage.hard_flags()` knew only two things: whether the
scrape fell back, and whether the content was under 400 characters. That let a
214-character stub reach the script writer, which is how a run ended up
fabricating an institution and narrating it as fact.

Everything here is pure and offline — no network, no model, no config.
"""

import re
from typing import Optional

# A page that scraped "successfully" but returned a consent wall, a paywall
# interstitial or a JS shell. The text is usually short AND matches one of
# these; either alone produces false positives (a good short post; an article
# legitimately *about* paywalls).
_STUB_MARKERS = (
    "enable javascript",
    "javascript is required",
    "please enable cookies",
    "accept cookies",
    "subscribe to continue",
    "subscribe to read",
    "create an account to",
    "sign in to continue",
    "you have reached your",
    "this content is for subscribers",
    "become a member to",
    "verifying you are human",
    "checking your browser",
    "access denied",
    "403 forbidden",
    "404 not found",
    "page not found",
    "are you a robot",
)

# Navigation/furniture lines that survive extraction. Used for the boilerplate
# ratio — the fraction of lines that are chrome rather than prose.
_BOILERPLATE_MARKERS = (
    "skip to content", "share this", "read more", "sign up", "log in",
    "newsletter", "all rights reserved", "privacy policy", "terms of service",
    "cookie", "follow us", "advertisement", "related articles", "trending",
    "©", "|", "»",
)


def _paragraphs(text: str) -> list:
    """Prose blocks, in the sense a reader would count them.

    `clean_content()` collapses newlines, so paragraph structure is often
    already gone by the time we see the text. Split on blank lines when they
    survive; otherwise treat sentence-dense runs as the unit.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) > 1:
        return [b for b in blocks if len(b) > 80]
    # Single collapsed block: approximate by grouping sentences in threes.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 40]
    return [" ".join(sentences[i:i + 3]) for i in range(0, len(sentences), 3)]


def _boilerplate_ratio(text: str) -> float:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return 0.0
    hits = sum(
        1
        for ln in lines
        if len(ln) < 120 and any(m in ln.lower() for m in _BOILERPLATE_MARKERS)
    )
    return round(hits / len(lines), 3)


def _looks_like_stub(text: str, chars: int) -> bool:
    """Short AND wall-shaped. Both conditions matter — see _STUB_MARKERS.

    Deliberately NOT length-only. A short genuine post ("We shipped a new
    compiler backend today") is not a paywall stub, and `summarize()` reports
    this flag to the model as "looks like a paywall/consent stub" — saying that
    about a real short post would be a lie. Shortness is already handled, twice
    over: `producibility_ceiling` caps anything under 400 chars, and the
    scrape-time gate stops it before triage.
    """
    if chars > 1500:
        return False
    low = text.lower()
    return any(m in low for m in _STUB_MARKERS)


def extract(
    content_clean: str,
    *,
    content_raw: str = "",
    source: str = "firecrawl",
    fallback: bool = False,
) -> dict:
    """Deterministic signals about a scrape.

    Args:
        content_clean: the cleaned text the pipeline will actually use
        content_raw: pre-clean text, for markdown-only signals (images, code)
        source: which retrieval path answered — firecrawl | wayback | hn_fallback
        fallback: True when the scrape failed and HN title/text was substituted

    Returns a JSON-serialisable dict, stored on the scrape step and on
    `triage_scores.scrape_signals`.
    """
    text = content_clean or ""
    raw = content_raw or text
    chars = len(text)
    words = len(text.split())
    paragraphs = _paragraphs(text)

    # Markdown-level signals survive only in the raw text; clean_content strips
    # the structure that makes them detectable.
    image_count = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", raw))
    link_count = len(re.findall(r"(?<!!)\[[^\]]*\]\([^)]+\)", raw))
    code_blocks = len(re.findall(r"```", raw)) // 2
    code_chars = sum(len(m) for m in re.findall(r"```.*?```", raw, re.S))
    heading_count = len(re.findall(r"^#{1,6}\s", raw, re.M))

    return {
        "chars": chars,
        "words": words,
        "paragraphs": len(paragraphs),
        "avg_paragraph_chars": (
            round(sum(len(p) for p in paragraphs) / len(paragraphs)) if paragraphs else 0
        ),
        "boilerplate_ratio": _boilerplate_ratio(raw),
        "code_ratio": round(code_chars / chars, 3) if chars else 0.0,
        "code_blocks": code_blocks,
        "image_count": image_count,
        "link_count": link_count,
        "heading_count": heading_count,
        "source": source,
        "fallback": bool(fallback),
        "looks_like_stub": _looks_like_stub(text, chars),
    }


def producibility_ceiling(signals: dict) -> Optional[int]:
    """A hard cap on `producibility` implied by the signals alone, or None.

    Deliberately a *ceiling*, not a score: the LLM judges what it can from the
    text, and this stops it scoring a stub highly no matter how interesting the
    headline sounds. These caps are the mechanism that keeps a 214-character
    scrape out of the script writer.
    """
    if signals.get("fallback") or signals.get("looks_like_stub"):
        return 15
    chars = signals.get("chars") or 0
    if chars < 400:
        return 20
    if chars < 1200:
        return 45
    if chars < 2500:
        return 70
    return None


def summarize(signals: dict) -> str:
    """One line for the LLM prompt — what we retrieved, so the model scores the
    material in front of it rather than the topic in the abstract."""
    parts = [
        f"{signals.get('chars', 0)} chars",
        f"{signals.get('words', 0)} words",
        f"{signals.get('paragraphs', 0)} paragraphs",
        f"retrieved via {signals.get('source', 'unknown')}",
    ]
    if signals.get("fallback"):
        parts.append("SCRAPE FAILED — this is HN title/text only, not the article")
    if signals.get("looks_like_stub"):
        parts.append("looks like a paywall/consent stub")
    if signals.get("code_ratio", 0) > 0.3:
        parts.append("mostly code")
    if signals.get("image_count"):
        parts.append(f"{signals['image_count']} images")
    return "; ".join(parts)
