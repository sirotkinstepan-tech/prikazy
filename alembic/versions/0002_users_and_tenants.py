"""add users and tenants

Revision ID: 0002_users_and_tenants
Revises: 0001_initial_schema
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_users_and_tenants"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenants (
            id uuid PRIMARY KEY,
            name text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE users (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            email text NOT NULL UNIQUE,
            password_hash text NOT NULL,
            full_name text NOT NULL,
            role text NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX ix_users_tenant_id ON users (tenant_id);
        CREATE INDEX ix_users_role ON users (role);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users;")
    op.execute("DROP TABLE IF EXISTS tenants;")
