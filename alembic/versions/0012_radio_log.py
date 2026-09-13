"""The station's running commentary: one row per thing a component did.

The studio page (plans/21) draws the station as a scene and needs to know,
as it happens, that the DJ asked for the next item, that the producer is
thinking, that the bank restocked. Track starts already live in
radio_events; this is everything else, short-lived and pruned.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "radio_log",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(), nullable=False),
        # dj | director | producer | bank | monitor | transmitter
        sa.Column("component", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    )
    op.create_index("ix_radio_log_at", "radio_log", ["at"])


def downgrade() -> None:
    op.drop_table("radio_log")
