"""Catalogue every generated image, whatever produced it.

Digest illustrations and covers had nowhere to live at all, and the segment
prompts that did exist in `segment_images` were unreachable beside them. One
table so "what have we drawn, in what style, at what cost" has one answer.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generated_images",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("run", sa.Integer(), nullable=True),
        sa.Column("seg", sa.Integer(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("style_key", sa.Text(), nullable=True),
        sa.Column("style_label", sa.Text(), nullable=True),
        sa.Column("technique", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("ink", sa.Float(), nullable=True),
        sa.Column("seconds", sa.Float(), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("thumb", sa.Text(), nullable=True),
    )
    op.create_index("ix_generated_images_kind", "generated_images", ["kind"])
    op.create_index("ix_generated_images_created_at", "generated_images", ["created_at"])
    op.create_index("ix_generated_images_item_id", "generated_images", ["item_id"])
    op.create_index("ix_generated_images_slug", "generated_images", ["slug"])
    op.create_index("ix_generated_images_style_key", "generated_images", ["style_key"])


def downgrade() -> None:
    op.drop_table("generated_images")
