"""add document filtering metadata

Revision ID: 20261124_0007
Revises: 20261124_0006
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261124_0007"
down_revision: str | None = "20261124_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("region", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("item_type", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_documents_region_item_type",
        "documents",
        ["region", "item_type"],
        unique=False,
    )
    op.execute(
        """
        UPDATE documents
        SET region = '常州市', item_type = '行政许可'
        WHERE id = 'cz-company-change-registration'
        """
    )
    op.execute(
        """
        UPDATE documents
        SET region = '常州市', item_type = '公共服务'
        WHERE id = 'cz-public-welfare-post-subsidy'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_documents_region_item_type", table_name="documents")
    op.drop_column("documents", "item_type")
    op.drop_column("documents", "region")
