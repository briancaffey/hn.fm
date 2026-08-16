"""Prompt provenance on pipeline steps + structured script on segments

Supports plans/08-llm-foundation.md:
  - pipeline_steps.prompt_name / prompt_version — which versioned prompt
    produced a step, so a quality change can be attributed to a prompt edit.
  - segments.script_json — the structured script (writer-chosen section
    boundaries, per-section beat + visual_intent). Nullable: segments written
    before this fall back to the legacy line-pair splitter.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-16

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

JSONVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("pipeline_steps", sa.Column("prompt_name", sa.Text(), nullable=True))
    op.add_column(
        "pipeline_steps", sa.Column("prompt_version", sa.Text(), nullable=True)
    )
    op.add_column("segments", sa.Column("script_json", JSONVariant, nullable=True))


def downgrade() -> None:
    op.drop_column("segments", "script_json")
    op.drop_column("pipeline_steps", "prompt_version")
    op.drop_column("pipeline_steps", "prompt_name")
