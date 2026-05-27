#!/usr/bin/env python3
"""Create a user with API token for prikazy."""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import AccessLevel
from app.repositories.users import UserRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Create API user and token")
    parser.add_argument("--tenant-id", required=True, type=UUID)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email")
    parser.add_argument(
        "--access-level",
        choices=[level.value for level in AccessLevel],
        default=AccessLevel.FULL_ACCESS.value,
        help="full_access = «Полный доступ» (required for AI queries)",
    )
    parser.add_argument("--token-name", default="cli")
    args = parser.parse_args()

    get_settings()
    session = SessionLocal()
    try:
        repository = UserRepository(session)
        user, raw_token = repository.create_user_with_token(
            tenant_id=args.tenant_id,
            name=args.name,
            email=args.email,
            access_level=AccessLevel(args.access_level),
            token_name=args.token_name,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"user_id={user.id}")
    print(f"access_level={user.access_level}")
    print(f"api_token={raw_token}")
    print("Save the token now — it will not be shown again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
