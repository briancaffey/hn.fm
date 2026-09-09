"""Source images: the article's own pictures, one row each (plans/18).

The v0 kept a JSON blob on the run row that nothing could list, filter or
join. A table means the question "what did we lift from this page, how big
was it, what did the vision model make of it, and what did that cost" has
one answer — and a restyled copy in `generated_images` can point back at the
picture it came from.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_images",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("run", sa.Integer(), nullable=False),
        # Position on the page, 1-based; also the file name.
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("alt", sa.Text(), nullable=True),
        # og:image | img | srcset — where on the page it was found.
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("sha1", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("stored_width", sa.Integer(), nullable=True),
        sa.Column("stored_height", sa.Integer(), nullable=True),
        sa.Column("stored_bytes", sa.Integer(), nullable=True),
        sa.Column("resized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("path", sa.Text(), nullable=True),
        # The vision pass. Null until analysed.
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.Column("subjects", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                  nullable=True),
        sa.Column("text_in_image", sa.Text(), nullable=True),
        sa.Column("interest", sa.Integer(), nullable=True),
        sa.Column("usable", sa.Boolean(), nullable=True),
        sa.Column("use_hint", sa.Text(), nullable=True),
        sa.Column("caveat", sa.Text(), nullable=True),
        sa.Column("analysis_model", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("analysis_seconds", sa.Float(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["item_id", "run"], ["runs.item_id", "runs.run"],
                                ondelete="CASCADE"),
    )
    op.create_index("ix_source_images_item_run", "source_images", ["item_id", "run"])
    op.create_index("ix_source_images_created_at", "source_images", ["created_at"])
    op.create_index("ix_source_images_kind", "source_images", ["kind"])
    # A restyled copy remembers which source picture it came from.
    op.add_column("generated_images",
                  sa.Column("source_image_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_generated_images_source_image_id", "generated_images",
                    ["source_image_id"])


def downgrade() -> None:
    op.drop_index("ix_generated_images_source_image_id", table_name="generated_images")
    op.drop_column("generated_images", "source_image_id")
    op.drop_table("source_images")
