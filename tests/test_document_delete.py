from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.models.document import Document
from app.models.storage_object import StorageObject
from app.services.document_service import DocumentService


class FakeStorage:
    def __init__(self):
        self.deleted: list[tuple[str, str]] = []

    def delete_object(self, *, bucket: str, object_key: str) -> None:
        self.deleted.append((bucket, object_key))


class FakeSession:
    def __init__(self, document: Document | None):
        self.document = document
        self.executed = []
        self.committed = False

    def execute(self, statement):
        self.executed.append(statement)
        return None

    def scalars(self, _statement):
        class Result:
            def __init__(self, values):
                self._values = values

            def __iter__(self):
                return iter(self._values)

        return Result([])

    def commit(self):
        self.committed = True


class FakeDocumentRepository:
    def __init__(self, document: Document | None, *, trash: str = "active"):
        self.document = document
        self.trash = trash

    def get_for_tenant(self, document_id, tenant_id, trash="active"):
        if self.document is None:
            return None
        if self.document.id != document_id or self.document.tenant_id != tenant_id:
            return None
        if trash == "active" and self.document.archived_at is not None:
            return None
        if trash == "trashed" and self.document.archived_at is None:
            return None
        return self.document

    def list_trashed_for_tenant(self, *, tenant_id, limit, offset):
        if self.document and self.document.tenant_id == tenant_id and self.document.archived_at:
            return [self.document], 1
        return [], 0


class FakeStorageObjectRepository:
    def __init__(self, storage_object: StorageObject):
        self.storage_object = storage_object
        self.deleted = []

    def list_by_ids(self, storage_object_ids):
        if self.storage_object.id in storage_object_ids:
            return [self.storage_object]
        return []

    def delete(self, storage_object):
        self.deleted.append(storage_object)


def _sample_document(*, in_trash: bool = False) -> Document:
    now = datetime.now(UTC)
    storage_id = uuid4()
    return Document(
        id=uuid4(),
        created_at=now,
        tenant_id=uuid4(),
        storage_object_id=storage_id,
        status="archived" if in_trash else "processed",
        doc_type="prikaz",
        mime_type="application/pdf",
        size_bytes=100,
        sha256="abc",
        updated_at=now,
        archived_at=now if in_trash else None,
    )


def _service(document: Document | None) -> DocumentService:
    storage_object = StorageObject(
        id=document.storage_object_id if document else uuid4(),
        bucket="documents",
        object_key="tenants/x/doc.pdf",
        sha256="abc",
        size_bytes=1,
        mime_type="application/pdf",
        original_filename="doc.pdf",
        created_at=datetime.now(UTC),
    )
    service = DocumentService(
        session=FakeSession(document),
        settings=Settings(),
        storage=FakeStorage(),
    )
    service.documents = FakeDocumentRepository(document)
    service.storage_objects = FakeStorageObjectRepository(storage_object)
    return service


def test_move_document_to_trash_sets_archived_at():
    document = _sample_document()
    service = _service(document)
    service.move_document_to_trash(document_id=document.id, tenant_id=document.tenant_id)
    assert document.archived_at is not None
    assert document.status == "archived"


def test_purge_document_requires_trash():
    document = _sample_document()
    service = _service(document)
    with pytest.raises(ApplicationError) as exc:
        service.purge_document(document_id=document.id, tenant_id=document.tenant_id)
    assert exc.value.code == "document_not_found"


def test_purge_document_removes_db_and_storage():
    document = _sample_document(in_trash=True)
    storage_object = StorageObject(
        id=document.storage_object_id,
        bucket="documents",
        object_key="tenants/x/doc.pdf",
        sha256=document.sha256,
        size_bytes=document.size_bytes,
        mime_type=document.mime_type,
        original_filename="doc.pdf",
        created_at=document.created_at,
    )
    session = FakeSession(document)
    storage = FakeStorage()
    storage_repo = FakeStorageObjectRepository(storage_object)
    service = DocumentService(session=session, settings=Settings(), storage=storage)
    service.documents = FakeDocumentRepository(document)
    service.storage_objects = storage_repo

    service.purge_document(document_id=document.id, tenant_id=document.tenant_id)

    assert session.committed is True
    assert len(session.executed) >= 6
    assert storage_repo.deleted == [storage_object]
    assert storage.deleted == [("documents", "tenants/x/doc.pdf")]


def test_restore_document_from_trash_clears_archived_at():
    document = _sample_document(in_trash=True)
    service = _service(document)
    service.restore_document_from_trash(document_id=document.id, tenant_id=document.tenant_id)
    assert document.archived_at is None
    assert document.status == "processed"
