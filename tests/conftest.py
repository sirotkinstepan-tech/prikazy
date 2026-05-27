import pytest

from app.core.config import Settings, get_settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        app_env="test",
        csrf_enabled=False,
        rate_limit_enabled=False,
        docs_enabled=True,
    )


@pytest.fixture
def client(test_settings, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)
    from app.main import create_app

    return __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(create_app())
