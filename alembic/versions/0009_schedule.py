"""Runtime settings and HN list churn samples.

`app_settings` is the small key/value store behind the two schedule overrides
(pause scraping, pause generation) and the last-run record of each scheduled
job. It is a table rather than Redis because the switches must survive a
broker restart and be visible to web, beat and every worker at once.

`hn_list_samples` records, every few minutes, how much the /new and /top lists
moved since the previous look. It exists to answer one question with data
instead of guesswork: how often is it worth fetching each list.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column(
            "value",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "hn_list_samples",
        sa.Column("list_name", sa.Text(), primary_key=True),
        sa.Column("sampled_at", sa.DateTime(), primary_key=True),
        sa.Column("size", sa.Integer(), nullable=False),
        # Ids not present in the previous sample of the same list. Null on
        # the first sample, when there is nothing to compare against.
        sa.Column("new_count", sa.Integer(), nullable=True),
        # Of the first 30 ids, how many changed since the previous sample —
        # the front page proper, for /top.
        sa.Column("front_changed", sa.Integer(), nullable=True),
        sa.Column("seconds_since_prev", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("hn_list_samples")
    op.drop_table("app_settings")
