"""Two-axis triage scoring + scrape signals + story briefs

Supports plans/09-story-brief-and-scoring.md:
  - triage_scores.interest / producibility — the split of the old blended
    `suitability`, which is kept (nullable-compatible) so rows scored before
    the split still read.
  - triage_scores.scrape_signals — the deterministic retrieval report that
    caps producibility.
  - story_briefs — one structured brief per run, consumed by the script room
    (plan 11) and art direction (plans 12/13).

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

JSONVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("triage_scores", sa.Column("interest", sa.Integer(), nullable=True))
    op.add_column(
        "triage_scores", sa.Column("producibility", sa.Integer(), nullable=True)
    )
    op.add_column(
        "triage_scores", sa.Column("scrape_signals", JSONVariant, nullable=True)
    )
    # Backfill interest from the old blend so the queue keeps its ordering for
    # already-scored stories. producibility stays NULL — it was never measured,
    # and inventing a value would make unscored rows look assessed.
    op.execute("UPDATE triage_scores SET interest = suitability WHERE interest IS NULL")

    op.create_table(
        "story_briefs",
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("run", sa.Integer(), primary_key=True),
        sa.Column("brief", JSONVariant, nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id", "run"], ["runs.item_id", "runs.run"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("story_briefs")
    op.drop_column("triage_scores", "scrape_signals")
    op.drop_column("triage_scores", "producibility")
    op.drop_column("triage_scores", "interest")
