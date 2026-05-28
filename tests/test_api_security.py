from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, require_web_user
from app.auth.service import AuthenticatedUser
from app.core.config import Settings
from app.core.section_permissions import resolve_access_for_role
from app.main import create_app
from app.models.enums import DocumentType, SectionAccessLevel, UserRole

DEFAULT_TENANT = UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _employee_view_prikaz_only() -> AuthenticatedUser:
    access = resolve_access_for_role(
        UserRole.EMPLOYEE,
        {DocumentType.PRIKAZ.value: SectionAccessLevel.VIEW_ONLY},
    )
    return AuthenticatedUser(
        id=uuid4(),
        tenant_id=DEFAULT_TENANT,
        email="employee@example.com",
        full_name="Employee",
        role=UserRole.EMPLOYEE,
        section_access=access,
    )


def _admin_user() -> AuthenticatedUser:
    access = resolve_access_for_role(UserRole.ADMIN, {})
    return AuthenticatedUser(
        id=uuid4(),
        tenant_id=DEFAULT_TENANT,
        email="admin@example.com",
        full_name="Admin",
        role=UserRole.ADMIN,
        section_access=access,
    )


@pytest.fixture
def authed_client(test_settings, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)
    app = create_app()
    return TestClient(app)


def test_documents_list_requires_auth(client: TestClient):
    response = client.get("/documents", params={"tenant_id": str(DEFAULT_TENANT)})
    assert response.status_code == 401


def test_search_requires_auth(client: TestClient):
    response = client.get("/search", params={"tenant_id": str(DEFAULT_TENANT), "q": "test"})
    assert response.status_code == 401


def test_documents_rejects_foreign_tenant(authed_client: TestClient):
    authed_client.app.dependency_overrides[get_current_user] = _admin_user
    response = authed_client.get(
        "/documents",
        params={"tenant_id": str(OTHER_TENANT), "limit": 1},
    )
    assert response.status_code == 403
    authed_client.app.dependency_overrides.clear()


def test_employee_portal_section_denied_returns_html(authed_client: TestClient):
    employee = _employee_view_prikaz_only()
    authed_client.app.dependency_overrides[require_web_user] = lambda: employee
    response = authed_client.get(
        "/portal/documents",
        params={"section": DocumentType.INTERNAL_CONTRACT.value},
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    assert "Нет доступа" in response.text
    authed_client.app.dependency_overrides.clear()


def test_employee_cannot_list_foreign_section(authed_client: TestClient):
    authed_client.app.dependency_overrides[get_current_user] = _employee_view_prikaz_only
    response = authed_client.get(
        "/documents",
        params={"doc_type": DocumentType.INTERNAL_CONTRACT.value, "limit": 1},
    )
    assert response.status_code == 403
    authed_client.app.dependency_overrides.clear()


def test_viewer_requires_login(client: TestClient):
    response = client.get("/viewer", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_openapi_disabled_when_docs_disabled(monkeypatch):
    from app.core.config import get_settings

    prod_settings = Settings(app_env="production", docs_enabled=False)
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: prod_settings)
    monkeypatch.setattr("app.main.get_settings", lambda: prod_settings)
    prod_app = create_app()
    assert prod_app.openapi_url is None


def test_openapi_protected_in_production(monkeypatch):
    from app.core.config import get_settings

    prod_settings = Settings(app_env="production", docs_enabled=True)
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: prod_settings)
    monkeypatch.setattr("app.main.get_settings", lambda: prod_settings)
    prod_app = create_app()
    assert prod_app.openapi_url is None
    paths = {route.path for route in prod_app.routes}
    assert "/docs" in paths
    assert "/openapi.json" in paths
