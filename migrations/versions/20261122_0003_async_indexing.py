"""add asynchronous indexing tasks

Revision ID: 20261122_0003
Revises: 20261122_0002
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_0003"
down_revision: str | None = "20261122_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "source_content",
            sa.LargeBinary(),
            nullable=False,
            server_default=sa.text("''::bytea"),
        ),
    )
    op.add_column("documents", sa.Column("index_task_id", sa.String(length=64), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "index_progress",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("documents", sa.Column("index_error", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE documents
        SET source_content = convert_to(content_text, 'UTF8'),
            status = 'ready',
            index_progress = 100
        WHERE content_text IS NOT NULL
        """
    )
    op.alter_column("documents", "content_text", existing_type=sa.Text(), nullable=True)

    op.create_table(
        "indexing_tasks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_indexing_tasks_document_status",
        "indexing_tasks",
        ["document_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_indexing_tasks_updated_at",
        "indexing_tasks",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_indexing_tasks_updated_at", table_name="indexing_tasks")
    op.drop_index("ix_indexing_tasks_document_status", table_name="indexing_tasks")
    op.drop_table("indexing_tasks")
    op.alter_column("documents", "content_text", existing_type=sa.Text(), nullable=False)
    op.drop_column("documents", "index_error")
    op.drop_column("documents", "index_progress")
    op.drop_column("documents", "index_task_id")
    op.drop_column("documents", "source_content")
