"""ai query usage logs

Revision ID: 0004_ai_query_logs
Revises: 0003_relations_section_access
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_ai_query_logs"
down_revision: str | Sequence[str] | None = "0003_relations_section_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ai_query_logs (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question_preview text,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX ix_ai_query_logs_user_created
            ON ai_query_logs (user_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_query_logs;")
