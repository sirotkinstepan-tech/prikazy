"""document uploader reference

Revision ID: 0005_document_created_by_user
Revises: 0004_ai_query_logs
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_document_created_by_user"
down_revision: str | Sequence[str] | None = "0004_ai_query_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS created_by_user_id uuid NULL REFERENCES users(id);

        CREATE INDEX IF NOT EXISTS ix_documents_created_by_user_id
            ON documents (created_by_user_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_documents_created_by_user_id;
        ALTER TABLE documents DROP COLUMN IF EXISTS created_by_user_id;
        """
    )
