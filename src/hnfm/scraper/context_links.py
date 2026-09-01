"""Following a *few* links off the submitted page.

A Hacker News submission is often a thin surface over the thing worth reading:
a blog post linking the paper, a release note linking the docs, a launch
announcement whose "About" page says who is actually behind it. Fetching those
turns a stub into a story.

The hard part is restraint. Crawling every link is slow, is rude to the sites
involved, and mostly dilutes the brief with navigation chrome. So this module
is deliberately conservative:

  * same-page links only — one hop, never recursive
  * scored by URL and anchor text against patterns that historically add
    context (paper, docs, about, author) and against patterns that never do
    (login, pricing, share, tag pages)
  * off-domain links are allowed but must look like a primary source, since a
    linked arXiv paper is the single most valuable follow there is
  * a hard cap, because the value of the third extra page is already low
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

MAX_FOLLOWED = 3

# Weighted because these are not equally informative: a linked paper is the
# story, an About page is background.
_VALUABLE = [
    (re.compile(r"arxiv\.org|doi\.org|/paper|\.pdf$|pubmed|biorxiv|nature\.com/articles", re.I), 5),
    (re.compile(r"/about|/who-we-are|/team|/mission", re.I), 3),
    (re.compile(r"/docs?/|/documentation|/readme|/spec", re.I), 3),
    (re.compile(r"github\.com/[^/]+/[^/]+/?$", re.I), 3),
    (re.compile(r"/author|/people/|/profile|/~", re.I), 2),
    (re.compile(r"/blog/20\d\d|/research|/publication", re.I), 2),
]

# Checked first: a URL matching any of these is never worth a fetch, whatever
# else it matches.
_JUNK = re.compile(
    r"(login|signin|signup|register|subscribe|pricing|cart|checkout|privacy"
    r"|terms|cookie|/tag/|/tags/|/category/|/categories/|/archive|/feed|\.rss"
    r"|/comments?|share|twitter\.com|x\.com|facebook\.com|linkedin\.com"
    r"|reddit\.com|news\.ycombinator\.com|mailto:|javascript:|#)",
    re.I,
)

_ANCHOR_VALUABLE = re.compile(
    r"\b(paper|preprint|study|about|documentation|docs|source|repository|"
    r"read more|full (?:report|paper|study)|methodology|author|whitepaper)\b",
    re.I,
)


@dataclass
class ContextPage:
    url: str
    title: str
    content: str
    reason: str


def _score(url: str, anchor: str) -> int:
    if _JUNK.search(url):
        return 0
    score = 0
    for pattern, weight in _VALUABLE:
        if pattern.search(url):
            score += weight
    if _ANCHOR_VALUABLE.search(anchor or ""):
        score += 2
    return score


def choose_links(
    base_url: str, links: List[dict], limit: int = MAX_FOLLOWED
) -> List[tuple]:
    """Pick the few links worth fetching. Returns [(url, reason)].

    `links` is [{"url": ..., "text": ...}]. Deduplicated by URL without
    fragment or query, since the same destination often appears several times
    with different tracking parameters and each fetch would be identical.
    """
    base_host = urlparse(base_url).netloc.lower()
    seen, scored = set(), []

    for link in links or []:
        raw = (link.get("url") or link.get("href") or "").strip()
        if not raw:
            continue
        absolute = urljoin(base_url, raw)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        key = f"{parsed.netloc}{parsed.path}".rstrip("/").lower()
        if not key or key in seen:
            continue

        anchor = (link.get("text") or "").strip()
        value = _score(absolute, anchor)
        if value <= 0:
            continue
        # Same-host pages are cheap context; off-host ones must clear a higher
        # bar so we follow a linked paper but not a random outbound mention.
        if parsed.netloc.lower() != base_host and value < 3:
            continue

        seen.add(key)
        scored.append((value, absolute, anchor[:60] or parsed.path))

    scored.sort(key=lambda t: -t[0])
    chosen = [(url, f"score {v}: {why}") for v, url, why in scored[:limit]]
    if chosen:
        logger.info(
            f"context: following {len(chosen)} of {len(links or [])} links — "
            + "; ".join(u for u, _ in chosen)
        )
    return chosen


def fetch_context(
    base_url: str, links: List[dict], scraper=None, limit: int = MAX_FOLLOWED
) -> List[ContextPage]:
    """Scrape the chosen links. Never raises — context is a bonus, not a step.

    A failure here must not fail the story: the submitted page already scraped
    fine, and losing an About page is not a reason to lose the article.
    """
    from .content_scraper import ContentScraper

    scraper = scraper or ContentScraper()
    pages: List[ContextPage] = []
    for url, reason in choose_links(base_url, links, limit=limit):
        try:
            scraped = scraper.scrape_url(url)
            body = (getattr(scraped, "content", "") or "").strip()
            if len(body) < 200:
                logger.debug(f"context: {url} too thin ({len(body)} chars), skipped")
                continue
            pages.append(ContextPage(
                url=url,
                title=getattr(scraped, "title", "") or url,
                # Capped hard: this is supporting material, and a long docs page
                # would otherwise crowd the article out of the prompt.
                content=body[:4000],
                reason=reason,
            ))
        except Exception as e:
            logger.info(f"context: {url} failed (non-fatal): {str(e)[:120]}")
    return pages


def as_prompt_block(pages: List[ContextPage], max_chars: int = 5000) -> str:
    if not pages:
        return "(no additional context pages were retrieved)"
    out, used = [], 0
    for p in pages:
        entry = f"[context: {p.title} — {p.url}]\n{p.content}"
        if used + len(entry) > max_chars:
            break
        out.append(entry)
        used += len(entry)
    return "\n\n".join(out)
