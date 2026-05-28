from uuid import uuid4

import pytest

from app.core.errors import ApplicationError
from app.models.enums import UserRole
from app.services.user_service import CreateUserCommand, UpdateUserCommand, UserService


class FakeSession:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


class FakeUserRepository:
    def __init__(self, existing_email: str | None = None):
        self.users = {}
        if existing_email:
            self.users[existing_email] = object()

    def get_by_email(self, email: str):
        return self.users.get(email)

    def add(self, user):
        self.users[user.email] = user
        return user

    def get_for_tenant(self, user_id, tenant_id):
        for user in self.users.values():
            if hasattr(user, "id") and user.id == user_id and user.tenant_id == tenant_id:
                return user
        return None


def test_create_user_validates_password_length():
    service = UserService(FakeSession())
    service.users = FakeUserRepository()

    with pytest.raises(ApplicationError) as exc:
        service.create_user(
            CreateUserCommand(
                tenant_id=uuid4(),
                email="new@example.com",
                password="123",
                full_name="Test User",
                role=UserRole.EMPLOYEE,
            )
        )
    assert exc.value.code == "password_too_short"


def test_create_user_validates_password_letters_and_digits():
    service = UserService(FakeSession())
    service.users = FakeUserRepository()

    with pytest.raises(ApplicationError) as exc:
        service.create_user(
            CreateUserCommand(
                tenant_id=uuid4(),
                email="new2@example.com",
                password="123456789",
                full_name="Test User",
                role=UserRole.EMPLOYEE,
            )
        )
    assert exc.value.code == "password_needs_letter_and_digit"


def test_create_user_rejects_duplicate_email():
    service = UserService(FakeSession())
    service.users = FakeUserRepository(existing_email="taken@example.com")

    with pytest.raises(ApplicationError) as exc:
        service.create_user(
            CreateUserCommand(
                tenant_id=uuid4(),
                email="taken@example.com",
                password="secret123",
                full_name="Test User",
                role=UserRole.EMPLOYEE,
            )
        )
    assert exc.value.code == "email_taken"
