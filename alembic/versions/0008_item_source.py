"""Remember which HN list an item arrived from.

`top` and `new` are materially different populations — `new` is unfiltered and
mostly noise, `top` has already survived the front page — so being unable to
tell them apart made the story list harder to reason about than it needed to
be.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hn_items", sa.Column("source", sa.Text(), nullable=True))
    op.create_index("ix_hn_items_source", "hn_items", ["source"])


def downgrade() -> None:
    op.drop_index("ix_hn_items_source", table_name="hn_items")
    op.drop_column("hn_items", "source")
