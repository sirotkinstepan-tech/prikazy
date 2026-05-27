from uuid import UUID

from app.core.config import Settings
from app.schemas.documents import DocumentRead


def document_file_url(*, document_id: UUID, disposition: str = "inline") -> str:
    return f"/documents/{document_id}/file?disposition={disposition}"


def document_download_url(*, document_id: UUID) -> str:
    return f"/documents/{document_id}/download"


def document_viewer_url(*, document_id: UUID) -> str:
    return f"/viewer?document_id={document_id}"


def absolute_api_url(settings: Settings, path: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def attach_document_links(document: DocumentRead, settings: Settings) -> DocumentRead:
    document.preview_url = absolute_api_url(
        settings,
        document_file_url(document_id=document.id, disposition="inline"),
    )
    document.download_url = absolute_api_url(
        settings,
        document_download_url(document_id=document.id),
    )
    document.viewer_url = absolute_api_url(
        settings,
        document_viewer_url(document_id=document.id),
    )
    return document
