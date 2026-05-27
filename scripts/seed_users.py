#!/usr/bin/env python3
"""Seed default tenant and users for local development."""

import sys
from uuid import UUID

from app.auth.service import AuthService
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.users import TenantRepository, UserRepository

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_TENANT_NAME = "Организация по умолчанию"

DEFAULT_USERS = [
    {
        "email": "admin@example.com",
        "password": "admin123",
        "full_name": "Администратор",
        "role": UserRole.ADMIN,
    },
    {
        "email": "employee@example.com",
        "password": "employee123",
        "full_name": "Иван Сотрудников",
        "role": UserRole.EMPLOYEE,
    },
]


def seed() -> None:
    session = SessionLocal()
    try:
        tenants = TenantRepository(session)
        users = UserRepository(session)
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
            if existing is not None:
                print(f"User already exists: {spec['email']}")
                continue
            user = User(
                tenant_id=DEFAULT_TENANT_ID,
                email=spec["email"],
                password_hash=auth.create_password_hash(spec["password"]),
                full_name=spec["full_name"],
                role=spec["role"],
            )
            users.add(user)
            print(f"Created user: {spec['email']} ({spec['role']}) — password: {spec['password']}")

        session.commit()
        print("Seed completed.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
    sys.exit(0)
