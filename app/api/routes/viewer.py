from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["viewer"])

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
_VIEWER_HTML = _STATIC_DIR / "viewer.html"


@router.get("/viewer", include_in_schema=False)
def document_viewer_page() -> FileResponse:
    return FileResponse(_VIEWER_HTML, media_type="text/html; charset=utf-8")
