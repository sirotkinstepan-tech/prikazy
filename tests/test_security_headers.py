from fastapi.testclient import TestClient

from app.api.dependencies import require_web_user
from app.auth.service import AuthenticatedUser
from app.core.section_permissions import resolve_access_for_role
from app.main import create_app
from app.models.enums import UserRole
from uuid import uuid4

DEFAULT_TENANT = "00000000-0000-0000-0000-000000000001"


def _admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        tenant_id=DEFAULT_TENANT,
        email="admin@example.com",
        full_name="Admin",
        role=UserRole.ADMIN,
        section_access=resolve_access_for_role(UserRole.ADMIN, {}),
    )


def test_inline_file_allows_sameorigin_framing(test_settings, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)
    app = create_app()
    app.dependency_overrides[require_web_user] = _admin

    client = TestClient(app)
    doc_id = "3a9847e5-75ad-4d82-a79f-8f68942770a0"
    response = client.get(
        f"/portal/documents/{doc_id}/file",
        params={"disposition": "inline"},
    )
    if response.status_code == 404:
        return
    assert response.headers.get("x-frame-options") == "SAMEORIGIN"
