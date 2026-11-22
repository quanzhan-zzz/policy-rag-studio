"""record evaluation dataset split

Revision ID: 20261122_0005
Revises: 20261122_0004
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_0005"
down_revision: str | None = "20261122_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("split", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_runs", "split")
