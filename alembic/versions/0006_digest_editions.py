"""Record which stories went into which digest edition

Two things need this. Deduplication: a reader should not meet the same story
twice across consecutive mornings, and the only way to know is to remember what
was sent. And provenance: when a digest reads badly, the first question is which
stories it drew on and when they were briefed.

Kept separate from `segments` because an edition is not a run — one edition
spans many stories, and one story appears in at most one edition per format.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

JSONVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "digest_editions",
        sa.Column("slug", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("shape", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("meta", JSONVariant, nullable=True),
    )
    op.create_table(
        "digest_edition_stories",
        sa.Column("slug", sa.Text(), primary_key=True),
        sa.Column("item_id", sa.BigInteger(), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["slug"], ["digest_editions.slug"], ondelete="CASCADE"),
    )
    # The dedup query is "which items appeared recently", so index the item.
    op.create_index(
        "ix_digest_edition_stories_item", "digest_edition_stories", ["item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_digest_edition_stories_item", "digest_edition_stories")
    op.drop_table("digest_edition_stories")
    op.drop_table("digest_editions")
