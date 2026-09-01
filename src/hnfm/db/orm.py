"""ORM models mirroring the Pydantic API models in web/models.py.

Composite natural primary keys — (item_id, run), (item_id, run, seg), … —
because every call site addresses entities by those tuples, exactly like the
old Redis key paths. Cascading FKs give delete_run/delete_segment for free.

JSON columns use JSONB on Postgres and plain JSON elsewhere (sqlite tests).
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class IdCounter(Base):
    """Atomic sequence counters, replacing Redis INCR.

    Run/seg numbers are allocated *before* their rows exist (the API allocates,
    then queues the task that creates the row), so MAX()+1 over the data tables
    would hand out duplicates. Scopes: "run:{item_id}", "seg:{item_id}:{run}".
    """

    __tablename__ = "id_counters"

    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class HNItemRow(Base):
    __tablename__ = "hn_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    type: Mapped[str] = mapped_column(Text, nullable=True)
    by: Mapped[str] = mapped_column(Text, nullable=True)
    time: Mapped[int] = mapped_column(BigInteger, nullable=True)  # unix seconds
    url: Mapped[str] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=True)
    descendants: Mapped[int] = mapped_column(Integer, nullable=True)
    kids: Mapped[list] = mapped_column(JSONVariant, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class RunRow(Base):
    __tablename__ = "runs"

    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hn_items.id", ondelete="CASCADE"), primary_key=True
    )
    run: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=True)
    content_raw: Mapped[str] = mapped_column(Text, nullable=True)
    content_clean: Mapped[str] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    short_description: Mapped[str] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONVariant, nullable=True)
    emoji: Mapped[list] = mapped_column(JSONVariant, nullable=True)
    haiku: Mapped[str] = mapped_column(Text, nullable=True)
    # Real images ingested from the article (was hnfm:item:{id}:run:{n}:source_images)
    source_images: Mapped[list] = mapped_column(JSONVariant, nullable=True)


class SegmentRow(Base):
    __tablename__ = "segments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "run"], ["runs.item_id", "runs.run"], ondelete="CASCADE"
        ),
    )

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run: Mapped[int] = mapped_column(Integer, primary_key=True)
    seg: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    # Flat `[S1] …` text — still the view the UI, ASR QA and legacy readers use.
    # Rendered from `script_json` when that exists.
    script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # The structured script (content.llm_schemas.Script): writer-chosen section
    # boundaries, per-section beat and visual_intent. NULL for segments written
    # before plans/08 — those fall back to the legacy line-pair splitter.
    script_json: Mapped[dict] = mapped_column(JSONVariant, nullable=True)

    style_theme: Mapped[str] = mapped_column(Text, nullable=True)
    style_theme_name: Mapped[str] = mapped_column(Text, nullable=True)
    aspect_format: Mapped[str] = mapped_column(Text, nullable=True)

    asr_qa: Mapped[dict] = mapped_column(JSONVariant, nullable=True)
    meta_plan: Mapped[list] = mapped_column(JSONVariant, nullable=True)

    sections_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    audio_combined_path: Mapped[str] = mapped_column(Text, nullable=True)
    audio_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    asr_json_path: Mapped[str] = mapped_column(Text, nullable=True)

    images_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    images_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    video_path: Mapped[str] = mapped_column(Text, nullable=True)
    subtitles_path: Mapped[str] = mapped_column(Text, nullable=True)
    video_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Audio-first: finished podcast episode (normalized MP3 with intro)
    episode_path: Mapped[str] = mapped_column(Text, nullable=True)


class SegmentSectionRow(Base):
    __tablename__ = "segment_sections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "run", "seg"],
            ["segments.item_id", "segments.run", "segments.seg"],
            ondelete="CASCADE",
        ),
    )

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run: Mapped[int] = mapped_column(Integer, primary_key=True)
    seg: Mapped[int] = mapped_column(Integer, primary_key=True)
    section: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_path: Mapped[str] = mapped_column(Text, nullable=True)
    cleaned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SegmentImageRow(Base):
    __tablename__ = "segment_images"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "run", "seg"],
            ["segments.item_id", "segments.run", "segments.seg"],
            ondelete="CASCADE",
        ),
    )

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run: Mapped[int] = mapped_column(Integer, primary_key=True)
    seg: Mapped[int] = mapped_column(Integer, primary_key=True)
    image_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    line_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str] = mapped_column(Text, nullable=True)
    sequence_paths: Mapped[list] = mapped_column(JSONVariant, nullable=True)
    video_clip_path: Mapped[str] = mapped_column(Text, nullable=True)
    video_clip_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TriageScoreRow(Base):
    """LLM suitability score for one processed run (the cheap text half).
    One score per run; the newest run's score represents the story."""

    __tablename__ = "triage_scores"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "run"], ["runs.item_id", "runs.run"], ondelete="CASCADE"
        ),
    )

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Legacy single blend (pre-plans/09). Kept so rows scored before the split
    # still read; new scores write it equal to `interest` for old consumers.
    suitability: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Two axes (plans/09). NULL on pre-split rows — readers fall back to
    # `suitability` for interest and treat producibility as unknown.
    interest: Mapped[int] = mapped_column(Integer, nullable=True)
    producibility: Mapped[int] = mapped_column(Integer, nullable=True)
    # Deterministic retrieval report from content/scrape_signals.py.
    scrape_signals: Mapped[dict] = mapped_column(JSONVariant, nullable=True)
    verdict: Mapped[str] = mapped_column(Text, nullable=True)  # great|good|marginal|unsuitable
    reasons: Mapped[list] = mapped_column(JSONVariant, nullable=True)
    flags: Mapped[list] = mapped_column(JSONVariant, nullable=True)
    topics: Mapped[list] = mapped_column(JSONVariant, nullable=True)
    visual_potential: Mapped[int] = mapped_column(Integer, nullable=True)
    narrative_potential: Mapped[int] = mapped_column(Integer, nullable=True)
    interest_match: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rank_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    model: Mapped[str] = mapped_column(Text, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class StoryFeedbackRow(Base):
    """Brian's call on a story — the human in the loop. Approve/star pins it
    to the top of triage, reject sinks it; notes explain why for future
    rubric tuning."""

    __tablename__ = "story_feedback"

    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hn_items.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(Text, nullable=True)  # starred|approved|rejected|None
    note: Mapped[str] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class StoryBriefRow(Base):
    """The structured Story Brief for one run (plans/09).

    The cheap text half's output artifact: framing, evidence and unknowns,
    consumed by the script room (plan 11) and the art direction (plans 12/13).
    One per run, replaced wholesale on re-run.
    """

    __tablename__ = "story_briefs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "run"], ["runs.item_id", "runs.run"], ondelete="CASCADE"
        ),
    )

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run: Mapped[int] = mapped_column(Integer, primary_key=True)
    brief: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PipelineStepRow(Base):
    """One unit of pipeline work: what ran, with which exact inputs, producing
    which outputs. `inputs` must be sufficient to re-run the step — that's what
    turns the audit trail into a control surface (plans/02-audit-trail.md).

    No FK to runs/segments: run-scoped steps (scrape, summary) are recorded
    before the run row exists, and the trail should survive entity deletion.
    Ordering within a run is by `id` (monotonic).
    """

    __tablename__ = "pipeline_steps"
    __table_args__ = (
        Index("ix_pipeline_steps_item_run_seg", "item_id", "run", "seg"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    item_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    run: Mapped[int] = mapped_column(Integer, nullable=False)
    seg: Mapped[int] = mapped_column(Integer, nullable=True)  # NULL = run-scoped
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="running"
    )  # running | ok | error | stale | superseded
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    seconds: Mapped[float] = mapped_column(Float, nullable=True)
    model: Mapped[str] = mapped_column(Text, nullable=True)
    # Which prompt produced this step, from the registry (plans/08). Recorded so
    # a quality change can be attributed to a specific prompt edit.
    prompt_name: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inputs: Mapped[dict] = mapped_column(JSONVariant, nullable=True)
    outputs: Mapped[dict] = mapped_column(JSONVariant, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    supersedes: Mapped[int] = mapped_column(BigInteger, nullable=True)


class PipelineMetricsRow(Base):
    """One observability record per render, keeping the exact dict shape the
    dashboard consumes in `data` (stages/counts/totals/ts). Superseded by
    pipeline_steps in plan 2."""

    __tablename__ = "pipeline_metrics"

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run: Mapped[int] = mapped_column(Integer, primary_key=True)
    seg: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_ts: Mapped[float] = mapped_column(Float, nullable=True)
    finished_ts: Mapped[float] = mapped_column(Float, nullable=True)


class DigestEditionRow(Base):
    """One published digest. See alembic 0006 for why editions are their own
    entity rather than a kind of run."""

    __tablename__ = "digest_editions"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    shape: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONVariant, nullable=True)


class DigestEditionStoryRow(Base):
    """Which stories an edition carried, and in what role.

    `role` records feature vs quick-hit so a story can be re-used in a
    different role later without reading identically — a story that was a
    30-second item is fair game as a feature once there is more to say.
    """

    __tablename__ = "digest_edition_stories"
    __table_args__ = (Index("ix_digest_edition_stories_item", "item_id"),)

    slug: Mapped[str] = mapped_column(
        Text, ForeignKey("digest_editions.slug", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=True)
