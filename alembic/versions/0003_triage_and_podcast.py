"""Triage scoring, human story feedback, podcast episode path

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

JSONVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "triage_scores",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("run", sa.Integer(), primary_key=True),
        sa.Column("suitability", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column("reasons", JSONVariant, nullable=True),
        sa.Column("flags", JSONVariant, nullable=True),
        sa.Column("topics", JSONVariant, nullable=True),
        sa.Column("visual_potential", sa.Integer(), nullable=True),
        sa.Column("narrative_potential", sa.Integer(), nullable=True),
        sa.Column("interest_match", sa.Float(), nullable=False),
        sa.Column("rank_score", sa.Float(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("scored_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id", "run"], ["runs.item_id", "runs.run"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_triage_scores_rank_score", "triage_scores", ["rank_score"])

    op.create_table(
        "story_feedback",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["hn_items.id"], ondelete="CASCADE"),
    )

    op.add_column("segments", sa.Column("episode_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("segments", "episode_path")
    op.drop_table("story_feedback")
    op.drop_index("ix_triage_scores_rank_score", table_name="triage_scores")
    op.drop_table("triage_scores")
