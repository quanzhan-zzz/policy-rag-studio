"""record reranker provider in evaluation snapshots

Revision ID: 20261122_0004
Revises: 20261122_0003
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_0004"
down_revision: str | None = "20261122_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("reranker_provider", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_runs", "reranker_provider")
