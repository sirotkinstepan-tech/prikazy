#!/usr/bin/env python3
"""Seed default tenant and users for local development."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.auth.service import AuthService
from app.core.document_sections import all_document_types
from app.db.session import SessionLocal
from app.models.enums import SectionAccessLevel, UserRole
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.user_section_access import UserSectionAccessRepository
from app.repositories.users import TenantRepository, UserRepository

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_TENANT_NAME = "Организация по умолчанию"

# Demo employee: view-only on all sections (including prikaz) for local testing.
DEMO_EMPLOYEE_SECTION_ACCESS: dict[str, SectionAccessLevel] = {
    doc_type.value: SectionAccessLevel.VIEW_ONLY for doc_type in all_document_types()
}

DEFAULT_USERS = [
    {
        "email": "admin@example.com",
        "password": "admin123",
        "full_name": "Администратор",
        "role": UserRole.ADMIN,
        "section_access": None,
    },
    {
        "email": "employee@example.com",
        "password": "employee123",
        "full_name": "Иван Сотрудников",
        "role": UserRole.EMPLOYEE,
        "section_access": DEMO_EMPLOYEE_SECTION_ACCESS,
    },
]


def _env_reset_passwords() -> bool:
    return os.environ.get("SEED_RESET_PASSWORDS", "").lower() in {"1", "true", "yes"}


def _ensure_employee_section_access(
    session,
    *,
    user_id: UUID,
    section_access_repo: UserSectionAccessRepository,
    access: dict[str, SectionAccessLevel],
) -> bool:
    stored = section_access_repo.list_for_user(user_id)
    if stored and any(level != SectionAccessLevel.NONE for level in stored.values()):
        return False
    section_access_repo.replace_for_user(user_id, access)
    return True


def seed(*, reset_passwords: bool = False) -> None:
    session = SessionLocal()
    try:
        tenants = TenantRepository(session)
        users = UserRepository(session)
        section_access_repo = UserSectionAccessRepository(session)
        auth = AuthService(session)

        tenant = tenants.get(DEFAULT_TENANT_ID)
        if tenant is None:
            tenant = Tenant(id=DEFAULT_TENANT_ID, name=DEFAULT_TENANT_NAME)
            tenants.add(tenant)
            print(f"Created tenant: {tenant.name} ({tenant.id})")
        else:
            print(f"Tenant already exists: {tenant.name}")

        for spec in DEFAULT_USERS:
            existing = users.get_by_email(spec["email"])
            if existing is None:
                user = User(
                    tenant_id=DEFAULT_TENANT_ID,
                    email=spec["email"],
                    password_hash=auth.create_password_hash(spec["password"]),
                    full_name=spec["full_name"],
                    role=spec["role"].value,
                )
                users.add(user)
                session.flush()
                if spec["role"] == UserRole.EMPLOYEE and spec["section_access"]:
                    section_access_repo.replace_for_user(user.id, spec["section_access"])
                print(
                    f"Created user: {spec['email']} ({spec['role'].value}) "
                    f"— password: {spec['password']}"
                )
                continue

            print(f"User already exists: {spec['email']}")
            if reset_passwords:
                existing.password_hash = auth.create_password_hash(spec["password"])
                print(f"  Reset password for {spec['email']} to seed default")
            if spec["role"] == UserRole.EMPLOYEE and spec["section_access"]:
                if _ensure_employee_section_access(
                    session,
                    user_id=existing.id,
                    section_access_repo=section_access_repo,
                    access=spec["section_access"],
                ):
                    print(f"  Applied demo section access for {spec['email']}")

        session.commit()
        print("Seed completed.")
        if not reset_passwords:
            print(
                "Note: existing user passwords were not changed. "
                "Use --reset-passwords or SEED_RESET_PASSWORDS=1 to restore seed defaults."
            )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Seed default tenant and dev users.")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Update passwords for default seed users to documented dev values.",
    )
    args = parser.parse_args(argv)
    seed(reset_passwords=args.reset_passwords or _env_reset_passwords())


if __name__ == "__main__":
    main()
    sys.exit(0)
