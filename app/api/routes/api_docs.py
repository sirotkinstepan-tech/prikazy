from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse

from app.api.dependencies import WebAdminDep
from app.core.config import Settings


def register_protected_api_docs(app: FastAPI, settings: Settings) -> None:
    """Swagger/ReDoc for production: only authenticated admins."""

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_json(_admin: WebAdminDep) -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False)
    def swagger_ui(_admin: WebAdminDep):
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.app_name} API",
        )

    @app.get("/redoc", include_in_schema=False)
    def redoc_ui(_admin: WebAdminDep):
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{settings.app_name} API",
        )
