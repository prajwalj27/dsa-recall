"""problem paused

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30

Moves "paused" from the FSRS card to the problem, so attempted-only problems (which have no
card) can be paused too. Existing paused cards become paused problems.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("problems", schema=None) as batch_op:
        batch_op.add_column(sa.Column("paused", sa.Boolean(), server_default="0", nullable=False))

    op.execute(
        "UPDATE problems SET paused = 1 WHERE slug IN (SELECT slug FROM cards WHERE suspended = 1)"
    )

    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_column("suspended")


def downgrade() -> None:
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("suspended", sa.Boolean(), server_default="0", nullable=False)
        )

    op.execute(
        "UPDATE cards SET suspended = 1 WHERE slug IN (SELECT slug FROM problems WHERE paused = 1)"
    )

    with op.batch_alter_table("problems", schema=None) as batch_op:
        batch_op.drop_column("paused")
