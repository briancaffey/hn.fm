"""Repository layer: every data operation the app performs, on Postgres.

Functions return the same Pydantic models (web/models.py) the app already
uses, so callers are agnostic to the storage backend. The legacy Redis-style
`key` fields on the Pydantic models are recomputed here to keep API response
shapes identical.
"""

import logging
from typing import List, Optional, Tuple

from sqlalchemy import Integer, case, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..web.models import HNItem, ProcessedRun, Segment, SegmentImage, SegmentSection
from .engine import db_session
from .orm import (
    StoryBriefRow,
    DigestEditionRow,
    DigestEditionStoryRow,
    HNItemRow,
    IdCounter,
    PipelineMetricsRow,
    RunRow,
    SegmentImageRow,
    SegmentRow,
    SegmentSectionRow,
    StoryFeedbackRow,
    TriageScoreRow,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Counters (Redis INCR replacement)
# ---------------------------------------------------------------------------

def next_counter(scope: str) -> int:
    """Atomically increment-and-return the counter for a scope."""
    with db_session() as s:
        if s.get_bind().dialect.name == "postgresql":
            stmt = (
                pg_insert(IdCounter)
                .values(scope=scope, value=1)
                .on_conflict_do_update(
                    index_elements=[IdCounter.scope],
                    set_={"value": IdCounter.value + 1},
                )
                .returning(IdCounter.value)
            )
            return int(s.execute(stmt).scalar_one())
        # Non-PG fallback (sqlite in tests): fine under test concurrency.
        row = s.get(IdCounter, scope)
        if row is None:
            row = IdCounter(scope=scope, value=1)
            s.add(row)
        else:
            row.value += 1
        s.flush()
        return int(row.value)


def bump_counter_to(scope: str, value: int) -> None:
    """Raise a counter to at least `value` (used by the backfill)."""
    with db_session() as s:
        row = s.get(IdCounter, scope)
        if row is None:
            s.add(IdCounter(scope=scope, value=value))
        elif row.value < value:
            row.value = value


# ---------------------------------------------------------------------------
# HN items
# ---------------------------------------------------------------------------

def _item_to_model(row: HNItemRow) -> HNItem:
    return HNItem(
        id=row.id,
        type=row.type,
        by=row.by,
        time=row.time,
        url=row.url,
        title=row.title,
        text=row.text,
        score=row.score,
        descendants=row.descendants,
        kids=row.kids,
    )


def upsert_item(item: HNItem) -> None:
    with db_session() as s:
        row = s.get(HNItemRow, item.id)
        if row is None:
            row = HNItemRow(id=item.id)
            s.add(row)
        row.type = item.type
        row.by = item.by
        row.time = item.time
        row.url = item.url
        row.title = item.title
        row.text = item.text
        row.score = item.score
        row.descendants = item.descendants
        row.kids = item.kids


def get_item(item_id: int) -> Optional[HNItem]:
    with db_session() as s:
        row = s.get(HNItemRow, item_id)
        return _item_to_model(row) if row else None


def exists_item(item_id: int) -> bool:
    with db_session() as s:
        return s.execute(
            select(HNItemRow.id).where(HNItemRow.id == item_id)
        ).scalar_one_or_none() is not None


def list_item_ids() -> List[int]:
    with db_session() as s:
        return list(
            s.execute(select(HNItemRow.id).order_by(HNItemRow.id.desc())).scalars()
        )


def list_items(offset: int, limit: int) -> List[HNItem]:
    with db_session() as s:
        rows = s.execute(
            select(HNItemRow).order_by(HNItemRow.id.desc()).offset(offset).limit(limit)
        ).scalars()
        return [_item_to_model(r) for r in rows]


def count_items() -> int:
    with db_session() as s:
        return int(s.execute(select(func.count(HNItemRow.id))).scalar_one())


def delete_item(item_id: int) -> bool:
    """Delete an item and (via cascade) its runs/segments/sections/images."""
    with db_session() as s:
        row = s.get(HNItemRow, item_id)
        if row is None:
            return False
        s.delete(row)
        return True


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def _run_to_model(row: RunRow) -> ProcessedRun:
    return ProcessedRun(
        key=f"hnfm:item:{row.item_id}:run:{row.run}",
        item_id=row.item_id,
        run=row.run,
        created_at=row.created_at,
        source_url=row.source_url or "",
        content_raw=row.content_raw or "",
        content_clean=row.content_clean or "",
        summary=row.summary or "",
        short_description=row.short_description or "",
        tags=row.tags or [],
        emoji=row.emoji or [],
        haiku=row.haiku or "",
    )


def save_run(pr: ProcessedRun) -> None:
    with db_session() as s:
        row = s.get(RunRow, (pr.item_id, pr.run))
        if row is None:
            row = RunRow(item_id=pr.item_id, run=pr.run, created_at=pr.created_at)
            s.add(row)
        row.created_at = pr.created_at
        row.source_url = pr.source_url
        row.content_raw = pr.content_raw
        row.content_clean = pr.content_clean
        row.summary = pr.summary
        row.short_description = pr.short_description
        row.tags = pr.tags
        row.emoji = pr.emoji
        row.haiku = pr.haiku


def get_run(item_id: int, run: int) -> Optional[ProcessedRun]:
    with db_session() as s:
        row = s.get(RunRow, (item_id, run))
        return _run_to_model(row) if row else None


def list_run_numbers(item_id: int, offset: int = 0, limit: int = 20) -> List[int]:
    """Run numbers for an item, newest-first (was LPUSH + LRANGE)."""
    with db_session() as s:
        return list(
            s.execute(
                select(RunRow.run)
                .where(RunRow.item_id == item_id)
                .order_by(RunRow.run.desc())
                .offset(offset)
                .limit(limit)
            ).scalars()
        )


def delete_run_row(item_id: int, run: int) -> bool:
    with db_session() as s:
        row = s.get(RunRow, (item_id, run))
        if row is None:
            return False
        s.delete(row)
        return True


def set_run_source_images(item_id: int, run: int, images: list) -> None:
    with db_session() as s:
        row = s.get(RunRow, (item_id, run))
        if row is None:
            raise RuntimeError(f"Run not found: {item_id}:{run}")
        row.source_images = images


def get_run_source_images(item_id: int, run: int) -> list:
    with db_session() as s:
        row = s.get(RunRow, (item_id, run))
        return (row.source_images if row else None) or []


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

def _segment_to_model(row: SegmentRow) -> Segment:
    return Segment(
        key=f"hnfm:seg:{row.item_id}:{row.run}:{row.seg}",
        item_id=row.item_id,
        run=row.run,
        seg=row.seg,
        created_at=row.created_at,
        processed_run_key=f"hnfm:item:{row.item_id}:run:{row.run}",
        script=row.script or "",
        script_json=row.script_json,
        style_theme=row.style_theme,
        style_theme_name=row.style_theme_name,
        aspect_format=row.aspect_format or "16:9",
        asr_qa=row.asr_qa,
        meta_plan=row.meta_plan,
        sections_total=row.sections_total or 0,
        audio_combined_path=row.audio_combined_path,
        audio_ready=bool(row.audio_ready),
        asr_json_path=row.asr_json_path,
        images_total=row.images_total or 0,
        images_ready=bool(row.images_ready),
        video_path=row.video_path,
        subtitles_path=row.subtitles_path,
        video_ready=bool(row.video_ready),
        episode_path=row.episode_path,
    )


def save_segment(seg_obj: Segment) -> None:
    with db_session() as s:
        row = s.get(SegmentRow, (seg_obj.item_id, seg_obj.run, seg_obj.seg))
        if row is None:
            row = SegmentRow(
                item_id=seg_obj.item_id,
                run=seg_obj.run,
                seg=seg_obj.seg,
                created_at=seg_obj.created_at,
            )
            s.add(row)
        row.created_at = seg_obj.created_at
        row.script = seg_obj.script
        row.script_json = seg_obj.script_json
        row.style_theme = seg_obj.style_theme
        row.style_theme_name = seg_obj.style_theme_name
        row.aspect_format = seg_obj.aspect_format
        row.asr_qa = seg_obj.asr_qa
        row.meta_plan = seg_obj.meta_plan
        row.sections_total = seg_obj.sections_total
        row.audio_combined_path = seg_obj.audio_combined_path
        row.audio_ready = seg_obj.audio_ready
        row.asr_json_path = seg_obj.asr_json_path
        row.images_total = seg_obj.images_total
        row.images_ready = seg_obj.images_ready
        row.video_path = seg_obj.video_path
        row.subtitles_path = seg_obj.subtitles_path
        row.video_ready = seg_obj.video_ready
        row.episode_path = seg_obj.episode_path


def get_segment(item_id: int, run: int, seg: int) -> Optional[Segment]:
    with db_session() as s:
        row = s.get(SegmentRow, (item_id, run, seg))
        return _segment_to_model(row) if row else None


def list_seg_numbers(item_id: int, run: int, offset: int = 0, limit: int = 20) -> List[int]:
    """Segment numbers for a run, newest-first."""
    with db_session() as s:
        return list(
            s.execute(
                select(SegmentRow.seg)
                .where(SegmentRow.item_id == item_id, SegmentRow.run == run)
                .order_by(SegmentRow.seg.desc())
                .offset(offset)
                .limit(limit)
            ).scalars()
        )


def list_all_segments(offset: int = 0, limit: int = 50) -> Tuple[List[Segment], int]:
    """All segments newest-first plus the total count (for pagination)."""
    with db_session() as s:
        total = int(s.execute(select(func.count()).select_from(SegmentRow)).scalar_one())
        rows = s.execute(
            select(SegmentRow)
            .order_by(SegmentRow.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).scalars()
        return [_segment_to_model(r) for r in rows], total


def delete_segment_row(item_id: int, run: int, seg: int) -> bool:
    with db_session() as s:
        row = s.get(SegmentRow, (item_id, run, seg))
        if row is None:
            return False
        s.delete(row)
        return True


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _section_to_model(row: SegmentSectionRow) -> SegmentSection:
    return SegmentSection(
        key=f"hnfm:seg:{row.item_id}:{row.run}:{row.seg}:sec:{row.section}",
        item_id=row.item_id,
        run=row.run,
        seg=row.seg,
        section=row.section,
        text=row.text,
        audio_path=row.audio_path,
        cleaned=bool(row.cleaned),
        duration_ms=row.duration_ms,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def save_section(meta: SegmentSection) -> None:
    with db_session() as s:
        row = s.get(
            SegmentSectionRow, (meta.item_id, meta.run, meta.seg, meta.section)
        )
        if row is None:
            row = SegmentSectionRow(
                item_id=meta.item_id,
                run=meta.run,
                seg=meta.seg,
                section=meta.section,
                text=meta.text,
                created_at=meta.created_at,
                updated_at=meta.updated_at,
            )
            s.add(row)
        row.text = meta.text
        row.audio_path = meta.audio_path
        row.cleaned = meta.cleaned
        row.duration_ms = meta.duration_ms
        row.created_at = meta.created_at
        row.updated_at = meta.updated_at


def get_section(item_id: int, run: int, seg: int, section: int) -> Optional[SegmentSection]:
    with db_session() as s:
        row = s.get(SegmentSectionRow, (item_id, run, seg, section))
        return _section_to_model(row) if row else None


def list_section_numbers(item_id: int, run: int, seg: int) -> List[int]:
    with db_session() as s:
        return list(
            s.execute(
                select(SegmentSectionRow.section)
                .where(
                    SegmentSectionRow.item_id == item_id,
                    SegmentSectionRow.run == run,
                    SegmentSectionRow.seg == seg,
                )
                .order_by(SegmentSectionRow.section.asc())
            ).scalars()
        )


def delete_sections(item_id: int, run: int, seg: int) -> None:
    """Remove all sections for a segment (rebuild-all clears then re-creates)."""
    with db_session() as s:
        s.execute(
            delete(SegmentSectionRow).where(
                SegmentSectionRow.item_id == item_id,
                SegmentSectionRow.run == run,
                SegmentSectionRow.seg == seg,
            )
        )


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def _image_to_model(row: SegmentImageRow) -> SegmentImage:
    return SegmentImage(
        key=f"hnfm:seg:{row.item_id}:{row.run}:{row.seg}:img:{row.image_index}",
        item_id=row.item_id,
        run=row.run,
        seg=row.seg,
        index=row.image_index,
        line_text=row.line_text,
        prompt=row.prompt,
        image_path=row.image_path,
        sequence_paths=row.sequence_paths,
        video_clip_path=row.video_clip_path,
        video_clip_seconds=row.video_clip_seconds,
        start_ms=row.start_ms,
        duration_ms=row.duration_ms,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def save_image(si: SegmentImage) -> None:
    with db_session() as s:
        row = s.get(SegmentImageRow, (si.item_id, si.run, si.seg, si.index))
        if row is None:
            row = SegmentImageRow(
                item_id=si.item_id,
                run=si.run,
                seg=si.seg,
                image_index=si.index,
                line_text=si.line_text,
                prompt=si.prompt,
                created_at=si.created_at,
                updated_at=si.updated_at,
            )
            s.add(row)
        row.line_text = si.line_text
        row.prompt = si.prompt
        row.image_path = si.image_path
        row.sequence_paths = si.sequence_paths
        row.video_clip_path = si.video_clip_path
        row.video_clip_seconds = si.video_clip_seconds
        row.start_ms = si.start_ms
        row.duration_ms = si.duration_ms
        row.created_at = si.created_at
        row.updated_at = si.updated_at


def get_image(item_id: int, run: int, seg: int, index: int) -> Optional[SegmentImage]:
    with db_session() as s:
        row = s.get(SegmentImageRow, (item_id, run, seg, index))
        return _image_to_model(row) if row else None


def list_image_indexes(item_id: int, run: int, seg: int) -> List[int]:
    with db_session() as s:
        return list(
            s.execute(
                select(SegmentImageRow.image_index)
                .where(
                    SegmentImageRow.item_id == item_id,
                    SegmentImageRow.run == run,
                    SegmentImageRow.seg == seg,
                )
                .order_by(SegmentImageRow.image_index.asc())
            ).scalars()
        )


# ---------------------------------------------------------------------------
# Aggregates for the UI (stories mission control, generations table)
# ---------------------------------------------------------------------------

STORY_SORT_KEYS = {
    "id": HNItemRow.id,
    "time": HNItemRow.time,
    "score": HNItemRow.score,
    "comments": HNItemRow.descendants,
}


def list_stories(
    offset: int = 0,
    limit: int = 50,
    sort: str = "id",
    direction: str = "desc",
    q: str = None,
    has_video: bool = None,
    has_runs: bool = None,
) -> Tuple[List[dict], int]:
    """Stories with generation aggregates: one row per item, JOINed counts.

    Sortable also by the aggregate keys: runs, segments, videos, latest.
    Returns (rows, total_after_filters).
    """
    runs_agg = (
        select(
            RunRow.item_id.label("item_id"),
            func.count(RunRow.run).label("runs_count"),
        )
        .group_by(RunRow.item_id)
        .subquery()
    )
    segs_agg = (
        select(
            SegmentRow.item_id.label("item_id"),
            func.count().label("segments_count"),
            func.sum(
                # portable boolean sum (sqlite lacks FILTER on older versions)
                func.coalesce(SegmentRow.video_ready.cast(Integer), 0)
            ).label("videos_count"),
            func.max(SegmentRow.created_at).label("latest_activity"),
        )
        .group_by(SegmentRow.item_id)
        .subquery()
    )

    runs_count = func.coalesce(runs_agg.c.runs_count, 0)
    segments_count = func.coalesce(segs_agg.c.segments_count, 0)
    videos_count = func.coalesce(segs_agg.c.videos_count, 0)

    query = (
        select(
            HNItemRow,
            runs_count.label("runs_count"),
            segments_count.label("segments_count"),
            videos_count.label("videos_count"),
            segs_agg.c.latest_activity,
        )
        .outerjoin(runs_agg, runs_agg.c.item_id == HNItemRow.id)
        .outerjoin(segs_agg, segs_agg.c.item_id == HNItemRow.id)
    )

    if q:
        query = query.where(HNItemRow.title.ilike(f"%{q}%"))
    if has_video is True:
        query = query.where(videos_count > 0)
    elif has_video is False:
        query = query.where(videos_count == 0)
    if has_runs is True:
        query = query.where(runs_count > 0)
    elif has_runs is False:
        query = query.where(runs_count == 0)

    sort_columns = {
        **STORY_SORT_KEYS,
        "runs": runs_count,
        "segments": segments_count,
        "videos": videos_count,
        "latest": segs_agg.c.latest_activity,
    }
    col = sort_columns.get(sort, HNItemRow.id)
    order = col.desc() if direction != "asc" else col.asc()
    # nulls last on desc so un-generated stories don't float on aggregate sorts
    query = query.order_by(order.nulls_last() if direction != "asc" else order,
                           HNItemRow.id.desc())

    with db_session() as s:
        total = int(
            s.execute(
                select(func.count()).select_from(query.subquery())
            ).scalar_one()
        )
        rows = s.execute(query.offset(offset).limit(limit)).all()
        out = []
        for item, n_runs, n_segs, n_videos, latest in rows:
            d = _item_to_model(item).model_dump()
            d.update(
                runs_count=int(n_runs or 0),
                segments_count=int(n_segs or 0),
                videos_count=int(n_videos or 0),
                latest_activity=latest.isoformat() if latest else None,
            )
            out.append(d)
        return out, total


def list_generations(item_id: int) -> List[dict]:
    """All segments for a story across all runs — one row per generation,
    joined with its run's summary. Newest first."""
    with db_session() as s:
        rows = s.execute(
            select(SegmentRow, RunRow.summary, RunRow.short_description)
            .join(
                RunRow,
                (RunRow.item_id == SegmentRow.item_id)
                & (RunRow.run == SegmentRow.run),
            )
            .where(SegmentRow.item_id == item_id)
            .order_by(SegmentRow.created_at.desc())
        ).all()
        out = []
        for seg_row, summary, short_description in rows:
            d = _segment_to_model(seg_row).model_dump()
            d["run_summary"] = summary or ""
            d["run_short_description"] = short_description or ""
            out.append(d)
        return out


# ---------------------------------------------------------------------------
# Triage scores + human story feedback
# ---------------------------------------------------------------------------

def save_triage_score(item_id: int, run: int, score: dict) -> None:
    from datetime import datetime as _dt

    with db_session() as s:
        row = s.get(TriageScoreRow, (item_id, run))
        if row is None:
            row = TriageScoreRow(item_id=item_id, run=run, scored_at=_dt.utcnow())
            s.add(row)
        # `interest` is the new primary axis; `suitability` is kept in step for
        # pre-plans/09 readers rather than left to drift.
        row.interest = int(score.get("interest") or 0)
        row.producibility = (
            int(score["producibility"]) if score.get("producibility") is not None else None
        )
        row.suitability = int(score.get("suitability") or score.get("interest") or 0)
        row.scrape_signals = score.get("scrape_signals")
        row.verdict = score.get("verdict")
        row.reasons = score.get("reasons")
        row.flags = score.get("flags")
        row.topics = score.get("topics")
        row.visual_potential = score.get("visual_potential")
        row.narrative_potential = score.get("narrative_potential")
        row.interest_match = float(score.get("interest_match") or 0.0)
        row.rank_score = float(score.get("rank_score") or 0.0)
        row.model = score.get("model")
        row.scored_at = _dt.utcnow()


def _triage_to_dict(row: TriageScoreRow) -> dict:
    return {
        "item_id": row.item_id,
        "run": row.run,
        "suitability": row.suitability,
        # Pre-plans/09 rows have no split scores: interest falls back to the
        # old blend, producibility stays None so the UI can show "unscored"
        # rather than implying a real measurement.
        "interest": row.interest if row.interest is not None else row.suitability,
        "producibility": row.producibility,
        "scrape_signals": row.scrape_signals,
        "verdict": row.verdict,
        "reasons": row.reasons or [],
        "flags": row.flags or [],
        "topics": row.topics or [],
        "visual_potential": row.visual_potential,
        "narrative_potential": row.narrative_potential,
        "interest_match": row.interest_match,
        "rank_score": row.rank_score,
        "model": row.model,
        "scored_at": row.scored_at.isoformat() if row.scored_at else None,
    }


def get_triage_score(item_id: int, run: int) -> Optional[dict]:
    with db_session() as s:
        row = s.get(TriageScoreRow, (item_id, run))
        return _triage_to_dict(row) if row else None


def save_story_feedback(item_id: int, verdict: Optional[str], note: Optional[str]) -> dict:
    from datetime import datetime as _dt

    with db_session() as s:
        row = s.get(StoryFeedbackRow, item_id)
        if row is None:
            row = StoryFeedbackRow(item_id=item_id, updated_at=_dt.utcnow())
            s.add(row)
        row.verdict = verdict
        row.note = note
        row.updated_at = _dt.utcnow()
        return {"item_id": item_id, "verdict": verdict, "note": note}


def get_story_feedback(item_id: int) -> Optional[dict]:
    with db_session() as s:
        row = s.get(StoryFeedbackRow, item_id)
        if not row:
            return None
        return {"item_id": row.item_id, "verdict": row.verdict, "note": row.note,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None}


# Human feedback boosts applied at query time so rubric re-scores never
# clobber Brian's calls: starred > approved > everything > rejected.
_FEEDBACK_BOOST = {"starred": 20000.0, "approved": 10000.0, "rejected": -20000.0}


def list_triage(
    offset: int = 0,
    limit: int = 50,
    verdict: str = None,
    include_generated: bool = False,
    include_rejected: bool = False,
    q: str = None,
    bucket: str = None,
) -> Tuple[List[dict], int]:
    """The ranked triage queue: newest score per story, joined with the item,
    human feedback, and generation counts. Ordered by effective rank
    (rank_score + human boost) descending."""
    # newest scored run per item
    latest = (
        select(
            TriageScoreRow.item_id.label("item_id"),
            func.max(TriageScoreRow.run).label("run"),
        )
        .group_by(TriageScoreRow.item_id)
        .subquery()
    )
    segs_agg = (
        select(
            SegmentRow.item_id.label("item_id"),
            func.count().label("segments_count"),
            func.sum(func.coalesce(SegmentRow.video_ready.cast(Integer), 0)).label(
                "videos_count"
            ),
        )
        .group_by(SegmentRow.item_id)
        .subquery()
    )

    boost = func.coalesce(
        case(
            (StoryFeedbackRow.verdict == "starred", _FEEDBACK_BOOST["starred"]),
            (StoryFeedbackRow.verdict == "approved", _FEEDBACK_BOOST["approved"]),
            (StoryFeedbackRow.verdict == "rejected", _FEEDBACK_BOOST["rejected"]),
            else_=0.0,
        ),
        0.0,
    )
    effective_rank = (TriageScoreRow.rank_score + boost).label("effective_rank")

    query = (
        select(
            TriageScoreRow,
            HNItemRow,
            StoryFeedbackRow.verdict.label("human_verdict"),
            StoryFeedbackRow.note.label("human_note"),
            func.coalesce(segs_agg.c.segments_count, 0).label("segments_count"),
            func.coalesce(segs_agg.c.videos_count, 0).label("videos_count"),
            effective_rank,
        )
        .join(
            latest,
            (latest.c.item_id == TriageScoreRow.item_id)
            & (latest.c.run == TriageScoreRow.run),
        )
        .join(HNItemRow, HNItemRow.id == TriageScoreRow.item_id)
        .outerjoin(StoryFeedbackRow, StoryFeedbackRow.item_id == TriageScoreRow.item_id)
        .outerjoin(segs_agg, segs_agg.c.item_id == TriageScoreRow.item_id)
    )

    if verdict:
        query = query.where(TriageScoreRow.verdict == verdict)
    if bucket == "needs_better_source":
        # High interest, low producibility — worth making, but the scrape was
        # too thin (plans/09). Thresholds live in config so this view tracks
        # whatever the scorer is actually using.
        from ..content import triage as _triage

        thresholds = (_triage._triage_config().get("buckets") or {})
        query = query.where(
            TriageScoreRow.interest
            >= int(thresholds.get("needs_source_min_interest", 65)),
            TriageScoreRow.producibility.isnot(None),
            TriageScoreRow.producibility
            <= int(thresholds.get("needs_source_max_producibility", 45)),
        )
    if not include_generated:
        query = query.where(func.coalesce(segs_agg.c.videos_count, 0) == 0)
    if not include_rejected:
        query = query.where(
            (StoryFeedbackRow.verdict.is_(None))
            | (StoryFeedbackRow.verdict != "rejected")
        )
    if q:
        query = query.where(HNItemRow.title.ilike(f"%{q}%"))

    query = query.order_by(effective_rank.desc(), TriageScoreRow.item_id.desc())

    with db_session() as s:
        total = int(
            s.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        )
        rows = s.execute(query.offset(offset).limit(limit)).all()
        out = []
        for (triage, item, human_verdict, human_note,
             segments_count, videos_count, eff_rank) in rows:
            d = _triage_to_dict(triage)
            d.update(
                title=item.title,
                url=item.url,
                by=item.by,
                time=item.time,
                hn_score=item.score,
                comments=item.descendants,
                human_verdict=human_verdict,
                human_note=human_note,
                segments_count=int(segments_count or 0),
                videos_count=int(videos_count or 0),
                effective_rank=float(eff_rank or 0.0),
            )
            out.append(d)
        return out, total


def list_episodes(offset: int = 0, limit: int = 100) -> Tuple[List[dict], int]:
    """Finished podcast episodes (segments with an episode MP3), newest first,
    joined with story title + run summary — feeds /api/podcast."""
    base = (
        select(SegmentRow, HNItemRow.title, RunRow.summary, RunRow.short_description)
        .join(HNItemRow, HNItemRow.id == SegmentRow.item_id)
        .join(
            RunRow,
            (RunRow.item_id == SegmentRow.item_id) & (RunRow.run == SegmentRow.run),
        )
        .where(SegmentRow.episode_path.is_not(None))
        .order_by(SegmentRow.created_at.desc())
    )
    with db_session() as s:
        total = int(
            s.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        )
        rows = s.execute(base.offset(offset).limit(limit)).all()
        out = []
        for seg_row, title, summary, short_description in rows:
            out.append({
                "item_id": seg_row.item_id,
                "run": seg_row.run,
                "seg": seg_row.seg,
                "title": title or f"HN {seg_row.item_id}",
                "summary": summary or "",
                "short_description": short_description or "",
                "episode_path": seg_row.episode_path,
                "created_at": seg_row.created_at.isoformat()
                if seg_row.created_at else None,
            })
        return out, total


def load_metrics(item_id: int, run: int, seg: int) -> Optional[dict]:
    with db_session() as s:
        row = s.get(PipelineMetricsRow, (item_id, run, seg))
        return dict(row.data) if row else None


def save_metrics(item_id: int, run: int, seg: int, data: dict, finalized: bool = None) -> None:
    with db_session() as s:
        row = s.get(PipelineMetricsRow, (item_id, run, seg))
        if row is None:
            row = PipelineMetricsRow(item_id=item_id, run=run, seg=seg, data=data)
            s.add(row)
        row.data = data
        row.started_ts = data.get("started_ts")
        row.finished_ts = data.get("finished_ts")
        if finalized is not None:
            row.finalized = finalized


def all_metrics_records(limit: int = 200) -> List[dict]:
    """Finalized records, newest first (was the hnfm:metrics:index set)."""
    with db_session() as s:
        rows = s.execute(
            select(PipelineMetricsRow.data)
            .where(PipelineMetricsRow.finalized.is_(True))
            .order_by(
                func.coalesce(
                    PipelineMetricsRow.finished_ts, PipelineMetricsRow.started_ts, 0
                ).desc()
            )
            .limit(limit)
        ).scalars()
        return [dict(d) for d in rows]


# ---------------------------------------------------------------------------
# Story briefs (plans/09)
# ---------------------------------------------------------------------------


def save_story_brief(item_id: int, run: int, brief: dict,
                     model: str = None, prompt_version: str = None) -> None:
    from datetime import datetime as _dt

    with db_session() as s:
        row = s.get(StoryBriefRow, (item_id, run))
        if row is None:
            row = StoryBriefRow(item_id=item_id, run=run, brief=brief,
                                created_at=_dt.utcnow())
            s.add(row)
        row.brief = brief
        row.model = model
        row.prompt_version = prompt_version
        row.created_at = _dt.utcnow()


def get_latest_story_brief(item_id: int) -> Optional[dict]:
    """The newest brief for a story, whichever run produced it.

    Briefs are keyed (item_id, run), but the run a story was last *scored* on
    is often not the run it was last *briefed* on — triage and generation
    advance independently. A reader only wants the most recent brief, so
    looking it up by run would miss one that plainly exists.
    """
    with db_session() as s:
        row = (
            s.query(StoryBriefRow)
            .filter(StoryBriefRow.item_id == item_id)
            .order_by(StoryBriefRow.run.desc())
            .first()
        )
        if not row:
            return None
        return {
            "item_id": row.item_id,
            "run": row.run,
            "brief": row.brief,
            "model": row.model,
            "prompt_version": row.prompt_version,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def get_story_brief(item_id: int, run: int) -> Optional[dict]:
    with db_session() as s:
        row = s.get(StoryBriefRow, (item_id, run))
        if not row:
            return None
        return {
            "item_id": row.item_id,
            "run": row.run,
            "brief": row.brief,
            "model": row.model,
            "prompt_version": row.prompt_version,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


# --- digest editions -------------------------------------------------------


def record_digest_edition(
    slug: str, title: str, shape: str, stories: list, meta: dict = None,
    sent: bool = False,
) -> None:
    """Remember what an edition contained, so the next one can avoid repeating it.

    Upsert on slug: rebuilding the same day's edition should replace its story
    list, not accumulate two overlapping sets that then both count as "recently
    seen" and starve tomorrow.
    """
    from datetime import datetime as _dt

    with db_session() as s:
        row = s.get(DigestEditionRow, slug)
        if row is None:
            row = DigestEditionRow(slug=slug, title=title, created_at=_dt.utcnow())
            s.add(row)
        row.title = title
        row.shape = shape
        row.meta = meta or {}
        if sent:
            row.sent_at = _dt.utcnow()
        s.query(DigestEditionStoryRow).filter(
            DigestEditionStoryRow.slug == slug
        ).delete()
        for position, (item_id, role) in enumerate(stories):
            s.add(DigestEditionStoryRow(
                slug=slug, item_id=item_id, position=position, role=role
            ))
        s.commit()


def recently_published_item_ids(days: int = 7) -> set:
    """Item ids carried by any edition in the last `days`.

    Time-boxed rather than forever: a story worth re-reading a month later is
    fine, and an unbounded exclusion list would eventually starve the digest.
    """
    from datetime import datetime as _dt, timedelta as _td

    cutoff = _dt.utcnow() - _td(days=days)
    with db_session() as s:
        rows = (
            s.query(DigestEditionStoryRow.item_id)
            .join(DigestEditionRow, DigestEditionRow.slug == DigestEditionStoryRow.slug)
            .filter(DigestEditionRow.created_at >= cutoff)
            .all()
        )
    return {r[0] for r in rows}
