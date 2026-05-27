from uuid import uuid4

import pytest

from app.auth.service import AuthenticatedUser
from app.core.errors import ApplicationError
from app.models.enums import DocumentType, SectionAccessLevel, UserRole
from app.web.section_access import ai_allowed_doc_types, require_ai_access


def test_ai_allowed_doc_types_for_admin():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="admin@example.com",
        full_name="Admin",
        role=UserRole.ADMIN,
        section_access={},
    )
    assert ai_allowed_doc_types(user) is None


def test_ai_allowed_doc_types_for_employee_with_full_on_prikaz():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        full_name="User",
        role=UserRole.EMPLOYEE,
        section_access={
            DocumentType.PRIKAZ.value: SectionAccessLevel.FULL,
            DocumentType.LNA.value: SectionAccessLevel.VIEW_ONLY,
        },
    )
    assert ai_allowed_doc_types(user) == [DocumentType.PRIKAZ.value]


def test_require_ai_access_denied_without_full():
    user = AuthenticatedUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        full_name="User",
        role=UserRole.EMPLOYEE,
        section_access={DocumentType.PRIKAZ.value: SectionAccessLevel.VIEW_ONLY},
    )
    with pytest.raises(ApplicationError) as exc_info:
        require_ai_access(user)
    assert exc_info.value.code == "ai_access_denied"
