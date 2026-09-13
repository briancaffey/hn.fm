"""HNFM on air: the run sheets a producer plans and the events the DJ reports.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "radio_sheets",
        sa.Column("sheet_id", sa.Text(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("items", JSON, nullable=False),
        # Index of the next item to serve.
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        # llm | fallback
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_radio_sheets_created_at", "radio_sheets", ["created_at"])
    op.create_table(
        "radio_events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        # "item:run:seg" for an episode.
        sa.Column("ref", sa.Text(), nullable=True),
        sa.Column("meta", JSON, nullable=True),
    )
    op.create_index("ix_radio_events_at", "radio_events", ["at"])


def downgrade() -> None:
    op.drop_table("radio_events")
    op.drop_table("radio_sheets")
