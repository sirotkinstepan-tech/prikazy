from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.errors import ApplicationError

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ERROR_TITLES: dict[str, str] = {
    "section_access_denied": "Нет доступа к разделу",
    "section_upload_denied": "Загрузка недоступна",
    "section_download_denied": "Скачивание недоступно",
    "section_links_denied": "Связи документов недоступны",
    "document_not_found": "Документ не найден",
    "user_not_found": "Пользователь не найден",
}


def _wants_html_response(request: Request) -> bool:
    path = request.url.path
    if path.startswith("/portal") or path.startswith("/admin"):
        return True
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower() and "application/json" not in accept.split(",")[0].lower()


def _back_url(request: Request) -> str:
    if request.url.path.startswith("/admin"):
        return "/admin/"
    if request.url.path.startswith("/portal"):
        return "/portal/"
    return "/"


def build_application_error_response(request: Request, exc: ApplicationError) -> Response:
    if not _wants_html_response(request):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "title": ERROR_TITLES.get(exc.code, "Ошибка"),
            "message": exc.message,
            "code": exc.code,
            "status_code": exc.status_code,
            "back_url": _back_url(request),
        },
        status_code=exc.status_code,
    )
