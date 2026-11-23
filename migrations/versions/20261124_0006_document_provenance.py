"""add document source provenance

Revision ID: 20261124_0006
Revises: 20261122_0005
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261124_0006"
down_revision: str | None = "20261122_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_name", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("source_retrieved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("documents", sa.Column("source_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "source_sha256")
    op.drop_column("documents", "source_retrieved_at")
    op.drop_column("documents", "source_url")
    op.drop_column("documents", "source_name")
