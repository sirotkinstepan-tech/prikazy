from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import admin_ui, ai_query, api_docs, auth_ui, documents, health, portal, search, sections, viewer
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.security import RateLimitMiddleware, SecurityHeadersMiddleware

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    show_docs = settings.docs_enabled
    public_docs = show_docs and not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
        docs_url="/docs" if public_docs else None,
        redoc_url="/redoc" if public_docs else None,
        openapi_url="/openapi.json" if public_docs else None,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        https_only=settings.session_https_only or settings.is_production,
        same_site="lax",
    )
    register_exception_handlers(app)

    if show_docs and settings.is_production:
        api_docs.register_protected_api_docs(app, settings)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(health.router)
    app.include_router(auth_ui.router)
    app.include_router(portal.router)
    app.include_router(admin_ui.router)
    app.include_router(viewer.router)
    app.include_router(sections.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(ai_query.router)
    return app


app = create_app()
