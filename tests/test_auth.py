from uuid import uuid4

import pytest

from app.core.errors import ApplicationError
from app.models.enums import AccessLevel
from app.models.user import User
from app.services.auth_service import AuthService, AuthenticatedUser
from app.services.llm_client import generate_api_token, hash_api_token


class FakeScalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class FakeSession:
    def __init__(self, token=None):
        self.token = token
        self.executed = False

    def scalars(self, _statement):
        return FakeScalars(self.token)

    def execute(self, _statement):
        self.executed = True


class FakeToken:
    def __init__(self, user: User, expires_at=None):
        self.id = uuid4()
        self.user = user
        self.expires_at = expires_at


def test_hash_api_token_is_deterministic():
    assert hash_api_token("abc") == hash_api_token("abc")
    assert hash_api_token("abc") != hash_api_token("def")


def test_generate_api_token_is_unique():
    assert generate_api_token() != generate_api_token()


def test_auth_service_rejects_invalid_token():
    session = FakeSession(token=None)
    with pytest.raises(ApplicationError) as exc_info:
        AuthService(session).authenticate("missing-token")
    assert exc_info.value.code == "invalid_token"


def test_auth_service_authenticates_active_user():
    user = User(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Admin",
        access_level=AccessLevel.FULL_ACCESS.value,
        is_active=True,
    )
    token = FakeToken(user)
    session = FakeSession(token=token)

    authenticated = AuthService(session).authenticate("raw-token")

    assert authenticated.access_level is AccessLevel.FULL_ACCESS
    assert session.executed is True


def test_auth_service_requires_full_access():
    tenant_id = uuid4()
    user = AuthenticatedUser(
        user_id=uuid4(),
        tenant_id=tenant_id,
        name="Reader",
        access_level=AccessLevel.READ,
    )

    with pytest.raises(ApplicationError) as exc_info:
        AuthService(FakeSession()).require_full_access(user, tenant_id)

    assert exc_info.value.code == "insufficient_permissions"
