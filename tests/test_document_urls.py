from datetime import UTC, datetime
from uuid import UUID

from app.api.document_urls import absolute_api_url, attach_document_links
from app.core.config import Settings
from app.schemas.documents import DocumentRead


def test_absolute_api_url_uses_public_base():
    settings = Settings(public_api_base_url="http://localhost:8001")
    assert (
        absolute_api_url(settings, "/documents/abc/file?tenant_id=1")
        == "http://localhost:8001/documents/abc/file?tenant_id=1"
    )


def test_attach_document_links_fills_viewer_preview_and_download():
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    settings = Settings(public_api_base_url="http://localhost:8001")
    now = datetime(2026, 5, 27, tzinfo=UTC)
    doc = DocumentRead(
        id=document_id,
        created_at=now,
        tenant_id=tenant_id,
        status="processed",
        mime_type="application/pdf",
        size_bytes=100,
        sha256="abc",
        updated_at=now,
    )

    attach_document_links(doc, settings)

    assert doc.viewer_url == (
        f"http://localhost:8001/viewer?tenant_id={tenant_id}&document_id={document_id}"
    )
    assert doc.preview_url.startswith("http://localhost:8001/documents/")
    assert "disposition=inline" in doc.preview_url
    assert doc.download_url == (
        f"http://localhost:8001/documents/{document_id}/download?tenant_id={tenant_id}"
    )
