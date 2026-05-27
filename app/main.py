from fastapi import FastAPI

from app.api.routes import ai_query, documents, health, search
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(ai_query.router)
    return app


app = create_app()
