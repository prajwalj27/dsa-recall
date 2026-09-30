"""solve rating source

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29 23:24:23.231257

Replaces solves.rating_inferred with rating_source (history / inferred / user), adds
used_solution ("Saw solution"), and allows at most one review_log row per solve.
Existing solves all came from the first backfill, so they become 'history'.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("solves", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rating_source", sa.String(), server_default="inferred", nullable=False)
        )
        batch_op.add_column(
            sa.Column("used_solution", sa.Boolean(), server_default="0", nullable=False)
        )
        batch_op.drop_column("rating_inferred")

    op.execute("UPDATE solves SET rating_source = 'history'")

    op.create_index("ux_review_log_solve_id", "review_log", ["solve_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_review_log_solve_id", table_name="review_log")

    with op.batch_alter_table("solves", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rating_inferred", sa.Boolean(), server_default="0", nullable=False)
        )
        batch_op.drop_column("used_solution")
        batch_op.drop_column("rating_source")
