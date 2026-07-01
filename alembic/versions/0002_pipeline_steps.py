"""pipeline_steps: per-step audit trail with replayable inputs

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

JSONVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "pipeline_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("run", sa.Integer(), nullable=False),
        sa.Column("seg", sa.Integer(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("step_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("seconds", sa.Float(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("llm_calls", sa.Integer(), nullable=False),
        sa.Column("inputs", JSONVariant, nullable=True),
        sa.Column("outputs", JSONVariant, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("supersedes", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_pipeline_steps_item_id", "pipeline_steps", ["item_id"])
    op.create_index(
        "ix_pipeline_steps_item_run_seg", "pipeline_steps", ["item_id", "run", "seg"]
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_steps_item_run_seg", table_name="pipeline_steps")
    op.drop_index("ix_pipeline_steps_item_id", table_name="pipeline_steps")
    op.drop_table("pipeline_steps")
