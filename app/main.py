from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import admin_ui, auth_ui, documents, health, portal, search, sections, viewer
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
    register_exception_handlers(app)

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
    return app


app = create_app()
