from datetime import date
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.services.document_service import DocumentService, UploadDocumentCommand, build_object_key


class FakeStorage:
    def __init__(self):
        self.uploads = []

    def upload_bytes(self, *, object_key: str, content: bytes, mime_type: str):
        from app.services.storage_service import StoredObject

        self.uploads.append((object_key, content, mime_type))
        return StoredObject(
            bucket="documents",
            object_key=object_key,
            version_id=None,
            size_bytes=len(content),
            mime_type=mime_type,
        )


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.committed = True

    def scalars(self, _statement):
        class Result:
            def first(self):
                return None

        return Result()


class FakeAsyncResult:
    id = "celery-task-id"


def test_upload_flow_creates_document_job_and_storage_metadata():
    settings = Settings()
    session = FakeSession()
    storage = FakeStorage()
    service = DocumentService(session=session, settings=settings, storage=storage)

    result = service.upload_document(
        UploadDocumentCommand(
            tenant_id=uuid4(),
            filename="invoice.pdf",
            content=b"hello invoice",
            mime_type="application/pdf",
            doc_type="prikaz",
            document_date=date(2026, 5, 14),
        ),
        enqueue_ocr_job=lambda job_id: FakeAsyncResult(),
    )

    assert result.status == "queued"
    assert storage.uploads
    assert session.committed is True
    assert {obj.__class__.__name__ for obj in session.added} >= {
        "StorageObject",
        "Document",
        "ProcessingJob",
        "ProcessingEvent",
    }


def test_upload_flow_rejects_missing_doc_type():
    settings = Settings()
    session = FakeSession()
    storage = FakeStorage()
    service = DocumentService(session=session, settings=settings, storage=storage)

    with pytest.raises(ApplicationError) as exc:
        service.upload_document(
            UploadDocumentCommand(
                tenant_id=uuid4(),
                filename="order.pdf",
                content=b"hello",
                mime_type="application/pdf",
            ),
            enqueue_ocr_job=lambda job_id: FakeAsyncResult(),
        )

    assert exc.value.code == "missing_doc_type"


def test_build_object_key_uses_tenant_date_document_and_hash():
    tenant_id = uuid4()
    document_id = uuid4()

    key = build_object_key(
        tenant_id=tenant_id,
        document_id=document_id,
        created_at=date(2026, 5, 14),
        sha256="abc123",
        filename="../../Invoice 1.pdf",
    )

    assert key.startswith(f"tenants/{tenant_id}/documents/2026/05/{document_id}/abc123-")
    assert ".." not in key
