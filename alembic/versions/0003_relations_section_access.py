"""document relations and per-section user access

Revision ID: 0003_relations_section_access
Revises: 0002_users_and_tenants
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_relations_section_access"
down_revision: str | Sequence[str] | None = "0002_users_and_tenants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE document_relations (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            from_document_id uuid NOT NULL,
            from_document_created_at timestamptz NOT NULL,
            to_document_id uuid NOT NULL,
            to_document_created_at timestamptz NOT NULL,
            link_label text,
            created_by_user_id uuid REFERENCES users(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_document_relation_pair UNIQUE (
                tenant_id,
                from_document_id,
                from_document_created_at,
                to_document_id,
                to_document_created_at
            )
        );

        CREATE INDEX ix_document_relations_tenant_from
            ON document_relations (tenant_id, from_document_id, from_document_created_at);
        CREATE INDEX ix_document_relations_tenant_to
            ON document_relations (tenant_id, to_document_id, to_document_created_at);

        CREATE TABLE user_section_access (
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            doc_type text NOT NULL,
            access_level text NOT NULL,
            PRIMARY KEY (user_id, doc_type)
        );

        CREATE INDEX ix_user_section_access_user_id ON user_section_access (user_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_section_access;")
    op.execute("DROP TABLE IF EXISTS document_relations;")
