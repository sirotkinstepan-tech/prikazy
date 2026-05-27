"""users and api tokens

Revision ID: 0002_users_and_api_tokens
Revises: 0001_initial_schema
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_users_and_api_tokens"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            email text NULL,
            name text NOT NULL,
            access_level text NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX ix_users_tenant_id ON users (tenant_id);
        CREATE INDEX ix_users_tenant_access_level ON users (tenant_id, access_level);

        CREATE TABLE api_tokens (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users(id),
            token_hash text NOT NULL UNIQUE,
            name text NOT NULL,
            last_used_at timestamptz NULL,
            expires_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX ix_api_tokens_user_id ON api_tokens (user_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS api_tokens CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        """
    )
