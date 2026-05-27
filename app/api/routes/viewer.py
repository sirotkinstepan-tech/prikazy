from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.api.dependencies import WebUserDep
from app.security.csrf import ensure_csrf_token

router = APIRouter(tags=["viewer"])

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
_VIEWER_HTML = _STATIC_DIR / "viewer.html"


@router.get("/viewer", include_in_schema=False)
def document_viewer_page(request: Request, user: WebUserDep) -> FileResponse:
    ensure_csrf_token(request)
    return FileResponse(_VIEWER_HTML, media_type="text/html; charset=utf-8")


@router.get("/auth/csrf", include_in_schema=False)
def csrf_token(request: Request, user: WebUserDep) -> dict[str, str]:
    return {"csrf_token": ensure_csrf_token(request)}
