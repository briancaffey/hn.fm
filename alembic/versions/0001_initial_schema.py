"""Initial schema: items, runs, segments, sections, images, metrics, counters

Revision ID: 0001
Revises:
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "id_counters",
        sa.Column("scope", sa.Text(), primary_key=True),
        sa.Column("value", sa.BigInteger(), nullable=False),
    )

    op.create_table(
        "hn_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("by", sa.Text(), nullable=True),
        sa.Column("time", sa.BigInteger(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("descendants", sa.Integer(), nullable=True),
        sa.Column("kids", JSONVariant, nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "runs",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("run", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("content_raw", sa.Text(), nullable=True),
        sa.Column("content_clean", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("tags", JSONVariant, nullable=True),
        sa.Column("emoji", JSONVariant, nullable=True),
        sa.Column("haiku", sa.Text(), nullable=True),
        sa.Column("source_images", JSONVariant, nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["hn_items.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "segments",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("run", sa.Integer(), primary_key=True),
        sa.Column("seg", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("style_theme", sa.Text(), nullable=True),
        sa.Column("style_theme_name", sa.Text(), nullable=True),
        sa.Column("aspect_format", sa.Text(), nullable=True),
        sa.Column("asr_qa", JSONVariant, nullable=True),
        sa.Column("meta_plan", JSONVariant, nullable=True),
        sa.Column("sections_total", sa.Integer(), nullable=False),
        sa.Column("audio_combined_path", sa.Text(), nullable=True),
        sa.Column("audio_ready", sa.Boolean(), nullable=False),
        sa.Column("asr_json_path", sa.Text(), nullable=True),
        sa.Column("images_total", sa.Integer(), nullable=False),
        sa.Column("images_ready", sa.Boolean(), nullable=False),
        sa.Column("video_path", sa.Text(), nullable=True),
        sa.Column("subtitles_path", sa.Text(), nullable=True),
        sa.Column("video_ready", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id", "run"], ["runs.item_id", "runs.run"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_segments_created_at", "segments", ["created_at"])

    op.create_table(
        "segment_sections",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("run", sa.Integer(), primary_key=True),
        sa.Column("seg", sa.Integer(), primary_key=True),
        sa.Column("section", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("audio_path", sa.Text(), nullable=True),
        sa.Column("cleaned", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id", "run", "seg"],
            ["segments.item_id", "segments.run", "segments.seg"],
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "segment_images",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("run", sa.Integer(), primary_key=True),
        sa.Column("seg", sa.Integer(), primary_key=True),
        sa.Column("image_index", sa.Integer(), primary_key=True),
        sa.Column("line_text", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("sequence_paths", JSONVariant, nullable=True),
        sa.Column("video_clip_path", sa.Text(), nullable=True),
        sa.Column("video_clip_seconds", sa.Float(), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id", "run", "seg"],
            ["segments.item_id", "segments.run", "segments.seg"],
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "pipeline_metrics",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("run", sa.Integer(), primary_key=True),
        sa.Column("seg", sa.Integer(), primary_key=True),
        sa.Column("data", JSONVariant, nullable=False),
        sa.Column("finalized", sa.Boolean(), nullable=False),
        sa.Column("started_ts", sa.Float(), nullable=True),
        sa.Column("finished_ts", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("pipeline_metrics")
    op.drop_table("segment_images")
    op.drop_table("segment_sections")
    op.drop_index("ix_segments_created_at", table_name="segments")
    op.drop_table("segments")
    op.drop_table("runs")
    op.drop_table("hn_items")
    op.drop_table("id_counters")
