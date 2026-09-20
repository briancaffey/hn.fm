"""radio sheets: ready_at — a block airs only once its lines are voiced.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("radio_sheets", sa.Column("ready_at", sa.DateTime(), nullable=True))
    # Everything planned so far has aired or been voiced: ready as of when it was made.
    op.execute("UPDATE radio_sheets SET ready_at = created_at WHERE ready_at IS NULL")


def downgrade() -> None:
    op.drop_column("radio_sheets", "ready_at")
