from uuid import UUID

from app.core.config import Settings
from app.schemas.documents import DocumentRead


def document_file_url(*, document_id: UUID, tenant_id: UUID, disposition: str = "inline") -> str:
    return (
        f"/documents/{document_id}/file"
        f"?tenant_id={tenant_id}&disposition={disposition}"
    )


def document_download_url(*, document_id: UUID, tenant_id: UUID) -> str:
    return f"/documents/{document_id}/download?tenant_id={tenant_id}"


def document_viewer_url(*, document_id: UUID, tenant_id: UUID) -> str:
    return f"/viewer?tenant_id={tenant_id}&document_id={document_id}"


def absolute_api_url(settings: Settings, path: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def attach_document_links(document: DocumentRead, settings: Settings) -> DocumentRead:
    document.preview_url = absolute_api_url(
        settings,
        document_file_url(
            document_id=document.id,
            tenant_id=document.tenant_id,
            disposition="inline",
        ),
    )
    document.download_url = absolute_api_url(
        settings,
        document_download_url(document_id=document.id, tenant_id=document.tenant_id),
    )
    document.viewer_url = absolute_api_url(
        settings,
        document_viewer_url(document_id=document.id, tenant_id=document.tenant_id),
    )
    return document
