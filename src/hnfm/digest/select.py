"""Choosing what goes in a digest.

Deliberately thin: `repo.list_triage()` is already the ranked queue the UI
shows, ordered by rank_score plus the human feedback boost. Reusing it means a
starred story rises in the digest exactly as it does on the triage page, and
there is one ranking implementation rather than two that drift.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DigestStory:
    item_id: int
    run: int
    title: str
    url: Optional[str]
    hn_score: int
    interest: Optional[int]
    rank: float
    brief: dict = field(default_factory=dict)

    @property
    def hn_url(self) -> str:
        return f"https://news.ycombinator.com/item?id={self.item_id}"


@dataclass
class Digest:
    title: str
    subtitle: str
    generated_at: datetime
    stories: List[DigestStory] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return f"digest-{self.generated_at:%Y-%m-%d}"


def select_stories(
    limit: int = 5,
    since_hours: Optional[int] = 24,
    require_brief: bool = True,
) -> Digest:
    """Top `limit` stories by effective rank, newest scores first.

    `require_brief` is on by default and is the important one: a story without
    a Story Brief has no body text to typeset, and including it would produce a
    headline followed by nothing. Such stories are skipped and logged rather
    than padded with the raw summary, so a thin digest is visibly thin instead
    of quietly filled with filler.
    """
    from ..db import repo

    # Over-fetch: the brief filter below can reject a large fraction, and
    # asking for exactly `limit` would silently under-fill the digest.
    #
    # include_generated=True: that flag exists to stop the *production* queue
    # re-offering stories already made into videos. A digest is for reading,
    # so having a video is irrelevant — and excluding them silently dropped
    # the highest-ranked stories, which are exactly the ones already produced.
    rows, _total = repo.list_triage(
        offset=0, limit=max(limit * 6, 30), include_generated=True
    )

    cutoff = (
        datetime.utcnow() - timedelta(hours=since_hours) if since_hours else None
    )

    stories: List[DigestStory] = []
    skipped_no_brief = 0
    for row in rows:
        if len(stories) >= limit:
            break
        item_id = row.get("item_id")
        run = row.get("run")
        if item_id is None or run is None:
            continue

        created = row.get("created_at") or row.get("scored_at")
        if cutoff and isinstance(created, datetime) and created < cutoff:
            continue

        # By latest brief, not by scored run: a story's newest score and its
        # newest brief routinely sit on different runs, and keying off `run`
        # here silently skipped stories whose brief plainly existed.
        # `.get("brief")` unwraps the row — the repo returns metadata around it.
        record = repo.get_latest_story_brief(item_id) or {}
        brief = record.get("brief") or {}
        if require_brief and not brief.get("thesis"):
            skipped_no_brief += 1
            continue

        stories.append(
            DigestStory(
                item_id=item_id,
                run=record.get("run") or run,
                title=row.get("title") or f"Item {item_id}",
                url=row.get("url"),
                hn_score=int(row.get("hn_score") or 0),
                interest=row.get("interest"),
                rank=float(row.get("effective_rank") or 0.0),
                brief=brief,
            )
        )

    if skipped_no_brief:
        logger.info(
            f"digest: skipped {skipped_no_brief} ranked stories with no Story Brief "
            f"(run triage on them to include them)"
        )
    if not stories:
        logger.warning(
            "digest: no stories had a Story Brief — nothing to typeset. "
            "Score some stories first (POST /api/hn/items/{id}/triage)."
        )

    now = datetime.now()
    return Digest(
        title="hn.fm Digest",
        subtitle=f"{len(stories)} stories · {now:%A %d %B %Y}",
        generated_at=now,
        stories=stories,
    )
