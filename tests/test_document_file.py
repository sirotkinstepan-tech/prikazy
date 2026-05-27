from uuid import uuid4

import pytest

from app.core.errors import ApplicationError
from app.services.document_content_service import DocumentContentService


class FakeStorageObject:
    bucket = "documents"
    object_key = "tenant/2026/05/doc.pdf"
    original_filename = "order.pdf"


class FakeDocument:
    def __init__(self):
        self.source_filename = "order.pdf"
        self.mime_type = "application/pdf"
        self.storage_object = FakeStorageObject()


class FakeRepository:
    def __init__(self, document):
        self.document = document

    def get_for_tenant(self, document_id, tenant_id):
        return self.document


class FakeStorage:
    def __init__(self, content: bytes):
        self.content = content
        self.calls = []

    def download_bytes(self, *, bucket: str, object_key: str) -> bytes:
        self.calls.append((bucket, object_key))
        return self.content


def test_load_file_returns_content(monkeypatch):
    document = FakeDocument()
    session = object()
    storage = FakeStorage(b"%PDF-1.4 test")

    monkeypatch.setattr(
        "app.services.document_content_service.DocumentRepository",
        lambda _session: FakeRepository(document),
    )

    service = DocumentContentService(session)
    result = service.load_file(
        document_id=uuid4(),
        tenant_id=uuid4(),
        storage=storage,  # type: ignore[arg-type]
    )

    assert result.content == b"%PDF-1.4 test"
    assert result.filename == "order.pdf"
    assert result.mime_type == "application/pdf"
    assert storage.calls == [("documents", "tenant/2026/05/doc.pdf")]


def test_load_file_raises_when_document_missing(monkeypatch):
    class EmptyRepository:
        def get_for_tenant(self, document_id, tenant_id):
            return None

    monkeypatch.setattr(
        "app.services.document_content_service.DocumentRepository",
        lambda _session: EmptyRepository(),
    )

    service = DocumentContentService(object())
    with pytest.raises(ApplicationError) as exc_info:
        service.load_file(
            document_id=uuid4(),
            tenant_id=uuid4(),
            storage=FakeStorage(b""),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404
