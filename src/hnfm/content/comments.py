"""Harvesting the Hacker News discussion, not just its size.

Until now the pipeline passed only `descendants` — the comment *count* — to the
model, while the brief schema invited facts with `source: "comment"`. With no
comment text in the prompt, that is an invitation to invent: observed output
included a fact attributed to `comment_id: 9207` on a story whose thread has no
such comment, and the count itself resurfaced as a "key number". Fetching the
thread is the fix; the schema was never the problem.

Ranking note: the Firebase API exposes no score for comments, so there is
nothing to sort by directly. `kids` order is HN's own ranking, which already
folds in votes, and it is by far the strongest signal available — position in
that list does most of the work here. The rest is shape: a comment with replies
started a conversation, and very short ones are usually agreement.
"""

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_API = "https://hacker-news.firebaseio.com/v0/item/{}.json"

# A thread is fetched one HTTP call per comment, so these bound both latency and
# how much politeness we owe the API. Top-level breadth matters more than depth:
# replies are usually correction or quibble, while the top level is where the
# distinct takes are.
MAX_TOP_LEVEL = 24
MAX_REPLIES_PER_TOP = 2
MAX_TOTAL = 48
_TIMEOUT = 15

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(text: Optional[str]) -> str:
    """HN serves comment text as HTML fragments; models read plain prose better."""
    if not text:
        return ""
    text = text.replace("<p>", "\n\n").replace("</p>", "")
    text = _TAG.sub("", text)
    return _WS.sub(" ", html.unescape(text)).strip()


def _fetch(item_id: int) -> Optional[dict]:
    try:
        r = requests.get(_API.format(item_id), timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        logger.debug(f"comments: fetch {item_id} failed (skipped): {e}")
        return None


def _fetch_many(ids: List[int]) -> List[dict]:
    if not ids:
        return []
    # Modest pool: this is someone else's free API, and the thread is not on the
    # critical path for anything a user is waiting on.
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [d for d in pool.map(_fetch, ids) if d]


def fetch_thread(item: dict, max_total: int = MAX_TOTAL) -> List[Dict]:
    """Top-level comments plus a couple of replies each, cleaned and flattened.

    `item` is the story's Firebase JSON (needs `kids`). Returns dicts with
    id / by / text / depth / replies / rank, ordered as HN ranks them. Deleted
    and dead comments are dropped — they carry no text and would otherwise
    occupy slots in the prompt.
    """
    kids = (item or {}).get("kids") or []
    if not kids:
        return []

    tops = _fetch_many(kids[:MAX_TOP_LEVEL])
    out: List[Dict] = []
    reply_ids: List[int] = []
    parent_of: Dict[int, int] = {}

    for rank, c in enumerate(tops):
        if c.get("deleted") or c.get("dead") or not c.get("text"):
            continue
        text = _clean(c.get("text"))
        if len(text) < 40:
            # Sub-40-character comments are "this", "+1", or a bare link. They
            # cost a prompt slot and contribute nothing to a brief.
            continue
        out.append({
            "id": c.get("id"), "by": c.get("by"), "text": text,
            "depth": 0, "replies": len(c.get("kids") or []), "rank": rank,
        })
        for kid in (c.get("kids") or [])[:MAX_REPLIES_PER_TOP]:
            reply_ids.append(kid)
            parent_of[kid] = c.get("id")

    for c in _fetch_many(reply_ids[: max(0, max_total - len(out))]):
        if c.get("deleted") or c.get("dead") or not c.get("text"):
            continue
        text = _clean(c.get("text"))
        if len(text) < 60:
            continue
        out.append({
            "id": c.get("id"), "by": c.get("by"), "text": text,
            "depth": 1, "replies": len(c.get("kids") or []),
            "rank": 1000 + len(out), "parent": parent_of.get(c.get("id")),
        })

    out.sort(key=lambda c: (c["depth"], c["rank"]))
    logger.info(
        f"comments: {len(out)} usable from {len(kids)} top-level ids "
        f"(item {item.get('id')})"
    )
    return out[:max_total]


def as_prompt_block(comments: List[Dict], max_chars: int = 6000) -> str:
    """Render comments for a prompt, with ids the model can actually cite.

    The id is included precisely so a claim attributed to a comment can be
    checked against this block afterwards — an attribution to an id that is not
    here is a fabrication, and `verify_comment_facts` treats it as one.
    """
    if not comments:
        return "(no comments were retrieved for this story)"
    lines, used = [], 0
    for c in comments:
        # Long comments are truncated rather than dropped: the opening of a
        # comment carries its claim, and keeping many voices beats keeping few
        # in full.
        body = c["text"][:900]
        entry = f"[comment {c['id']} by {c.get('by') or 'unknown'}] {body}"
        if used + len(entry) > max_chars:
            break
        lines.append(entry)
        used += len(entry)
    return "\n\n".join(lines)


def verify_comment_facts(facts: List[dict], comments: List[Dict]) -> List[dict]:
    """Drop comment-sourced facts that cite an id we never retrieved.

    The article-sourced half of this check already exists in story_brief; this
    is its counterpart, and the reason comment ids are surfaced to the model at
    all. Facts citing no id are kept only if their quote appears in some
    comment, so a real observation with sloppy attribution survives while an
    invented one does not.
    """
    if not facts:
        return []
    by_id = {str(c["id"]): c["text"] for c in comments}
    corpus = " ".join(by_id.values()).lower()
    kept = []
    for fact in facts:
        if (fact.get("source") or "").lower() != "comment":
            kept.append(fact)
            continue
        cid = str(fact.get("comment_id") or "").strip()
        quote = (fact.get("quote") or "").strip().lower()
        if cid and cid in by_id:
            kept.append(fact)
            continue
        if quote and len(quote) > 24 and quote[:120] in corpus:
            kept.append(fact)
            continue
        logger.info(
            f"comments: dropped unverifiable comment fact "
            f"(id={cid or 'none'}) — {str(fact.get('claim'))[:70]}"
        )
    return kept
