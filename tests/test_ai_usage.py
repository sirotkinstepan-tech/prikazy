from datetime import date
from uuid import uuid4

import pytest

from app.auth.service import AuthenticatedUser
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.models.enums import DocumentType, SectionAccessLevel, UserRole
from app.services.ai_usage_service import AiUsageService
from app.web.section_access import ai_access_mode, ai_allowed_doc_types, require_ai_access


class FakeResult:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one(self):
        return self._scalar


class FakeSession:
    def __init__(self, count=0):
        self.count = count
        self.added = []

    def execute(self, statement, params):
        return FakeResult(scalar=self.count)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None


def test_ai_access_mode_limited_for_upload_view_download():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        full_name="User",
        role=UserRole.EMPLOYEE,
        section_access={
            DocumentType.PRIKAZ.value: SectionAccessLevel.UPLOAD_VIEW_DOWNLOAD,
        },
    )
    assert ai_access_mode(user) == "limited"
    assert ai_allowed_doc_types(user) == [DocumentType.PRIKAZ.value]


def test_ai_access_mode_unlimited_for_full():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        full_name="User",
        role=UserRole.EMPLOYEE,
        section_access={
            DocumentType.PRIKAZ.value: SectionAccessLevel.FULL,
        },
    )
    assert ai_access_mode(user) == "unlimited"


def test_ai_access_denied_without_upload_and_download():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        full_name="User",
        role=UserRole.EMPLOYEE,
        section_access={
            DocumentType.PRIKAZ.value: SectionAccessLevel.VIEW_DOWNLOAD,
            DocumentType.LNA.value: SectionAccessLevel.UPLOAD_VIEW,
        },
    )
    assert ai_access_mode(user) == "none"
    with pytest.raises(ApplicationError) as exc_info:
        require_ai_access(user)
    assert exc_info.value.code == "ai_access_denied"


def test_consume_query_enforces_monthly_limit():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        full_name="User",
        role=UserRole.EMPLOYEE,
        section_access={
            DocumentType.PRIKAZ.value: SectionAccessLevel.UPLOAD_VIEW_DOWNLOAD,
        },
    )
    service = AiUsageService(FakeSession(count=100), Settings(ai_monthly_query_limit=100))
    with pytest.raises(ApplicationError) as exc_info:
        service.consume_query(user, question="test")
    assert exc_info.value.code == "ai_quota_exceeded"


def test_consume_query_allows_unlimited_for_full_access():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        full_name="User",
        role=UserRole.EMPLOYEE,
        section_access={
            DocumentType.PRIKAZ.value: SectionAccessLevel.FULL,
        },
    )
    session = FakeSession(count=500)
    service = AiUsageService(session, Settings(ai_monthly_query_limit=100))
    status = service.consume_query(user, question="test question")
    assert status.is_unlimited
    assert len(session.added) == 1
