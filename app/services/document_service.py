import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.document_sections import validate_doc_type
from app.core.errors import ApplicationError
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_relation import DocumentRelation
from app.models.enums import DocumentStatus, ProcessingJobStatus, ProcessingJobType
from app.models.extracted_field import ExtractedField
from app.models.ocr_result import OcrResult
from app.models.processing_event import ProcessingEvent
from app.models.processing_job import ProcessingJob
from app.models.storage_object import StorageObject
from app.repositories.documents import DocumentRepository
from app.repositories.events import ProcessingEventRepository
from app.repositories.jobs import ProcessingJobRepository
from app.repositories.storage_objects import StorageObjectRepository
from app.services.file_validation import validate_file_signature
from app.services.mime_types import resolve_mime_type
from app.services.storage_service import ObjectStorageService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadDocumentCommand:
    tenant_id: UUID
    filename: str
    content: bytes
    mime_type: str
    doc_type: str | None = None
    document_date: date | None = None
    counterparty_name: str | None = None
    title: str | None = None
    created_by_user_id: UUID | None = None


@dataclass(frozen=True)
class UploadDocumentResult:
    document_id: UUID
    document_created_at: datetime
    status: str
    job_id: UUID


def safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned or "document"


def build_object_key(
    *,
    tenant_id: UUID,
    document_id: UUID,
    created_at: datetime,
    sha256: str,
    filename: str,
) -> str:
    return (
        f"tenants/{tenant_id}/documents/{created_at:%Y}/{created_at:%m}/"
        f"{document_id}/{sha256}-{safe_filename(filename)}"
    )


class DocumentService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        storage: ObjectStorageService,
    ):
        self.session = session
        self.settings = settings
        self.storage = storage
        self.documents = DocumentRepository(session)
        self.storage_objects = StorageObjectRepository(session)
        self.jobs = ProcessingJobRepository(session)
        self.events = ProcessingEventRepository(session)

    def upload_document(
        self,
        command: UploadDocumentCommand,
        *,
        enqueue_ocr_job: Callable[[str], object],
    ) -> UploadDocumentResult:
        resolved_mime_type = resolve_mime_type(command.mime_type, command.filename)
        command = UploadDocumentCommand(
            tenant_id=command.tenant_id,
            filename=command.filename,
            content=command.content,
            mime_type=resolved_mime_type,
            doc_type=command.doc_type,
            document_date=command.document_date,
            counterparty_name=command.counterparty_name,
            title=command.title,
            created_by_user_id=command.created_by_user_id,
        )
        self._validate_upload(command)
        now = datetime.now(UTC)
        document_id = uuid4()
        sha256 = hashlib.sha256(command.content).hexdigest()
        duplicate = self.documents.find_duplicate(command.tenant_id, sha256)
        object_key = build_object_key(
            tenant_id=command.tenant_id,
            document_id=document_id,
            created_at=now,
            sha256=sha256,
            filename=command.filename,
        )

        stored = self.storage.upload_bytes(
            object_key=object_key,
            content=command.content,
            mime_type=command.mime_type,
        )
        storage_object = StorageObject(
            id=uuid4(),
            bucket=stored.bucket,
            object_key=stored.object_key,
            version_id=stored.version_id,
            sha256=sha256,
            size_bytes=stored.size_bytes,
            mime_type=command.mime_type,
            original_filename=command.filename,
            created_at=now,
        )
        document = Document(
            id=document_id,
            created_at=now,
            tenant_id=command.tenant_id,
            storage_object_id=storage_object.id,
            status=DocumentStatus.QUEUED.value,
            doc_type=command.doc_type,
            document_date=command.document_date,
            counterparty_name=command.counterparty_name,
            title=command.title,
            source_filename=command.filename,
            mime_type=command.mime_type,
            size_bytes=stored.size_bytes,
            sha256=sha256,
            updated_at=now,
            created_by_user_id=command.created_by_user_id,
        )
        job = ProcessingJob(
            id=uuid4(),
            document_id=document.id,
            document_created_at=document.created_at,
            job_type=ProcessingJobType.OCR.value,
            status=ProcessingJobStatus.QUEUED.value,
            created_at=now,
            updated_at=now,
        )

        self.storage_objects.add(storage_object)
        self.documents.add(document)
        self.session.flush()
        self.jobs.add(job)
        self.session.flush()
        self.events.add(
            document_id=document.id,
            document_created_at=document.created_at,
            job_id=job.id,
            event_type="document.queued",
            message="Document uploaded and queued for OCR",
            payload={
                "storage_object_id": str(storage_object.id),
                "duplicate_document_id": str(duplicate.id) if duplicate else None,
            },
        )
        self.session.flush()

        async_result = enqueue_ocr_job(str(job.id))
        self.jobs.set_celery_task_id(job, getattr(async_result, "id", None))
        self.session.commit()
        logger.info(
            "uploaded document",
            extra={"document_id": str(document.id), "job_id": str(job.id)},
        )
        return UploadDocumentResult(
            document_id=document.id,
            document_created_at=document.created_at,
            status=document.status,
            job_id=job.id,
        )

    def _validate_upload(self, command: UploadDocumentCommand) -> None:
        if command.mime_type not in self.settings.allowed_mime_type_set:
            raise ApplicationError(
                f"Unsupported MIME type: {command.mime_type}",
                status_code=415,
                code="unsupported_mime_type",
            )
        if not command.content:
            raise ApplicationError("Uploaded file is empty", status_code=400, code="empty_file")
        if len(command.content) > self.settings.max_upload_size_bytes:
            raise ApplicationError(
                "Uploaded file exceeds size limit",
                status_code=413,
                code="file_too_large",
            )
        if command.doc_type is None:
            raise ApplicationError(
                "doc_type is required",
                status_code=400,
                code="missing_doc_type",
            )
        validate_doc_type(command.doc_type)
        validate_file_signature(mime_type=command.mime_type, content=command.content)

    def move_document_to_trash(self, *, document_id: UUID, tenant_id: UUID) -> None:
        document = self.documents.get_for_tenant(document_id, tenant_id, trash="active")
        if document is None:
            raise ApplicationError(
                "Document not found",
                status_code=404,
                code="document_not_found",
            )
        now = datetime.now(UTC)
        document.archived_at = now
        document.status = DocumentStatus.ARCHIVED.value
        document.updated_at = now
        self.session.commit()
        logger.info("moved document to trash", extra={"document_id": str(document.id)})

    def restore_document_from_trash(self, *, document_id: UUID, tenant_id: UUID) -> None:
        document = self.documents.get_for_tenant(document_id, tenant_id, trash="trashed")
        if document is None:
            raise ApplicationError(
                "Document not found in trash",
                status_code=404,
                code="document_not_found",
            )
        document.archived_at = None
        if document.status == DocumentStatus.ARCHIVED.value:
            document.status = DocumentStatus.PROCESSED.value
        document.updated_at = datetime.now(UTC)
        self.session.commit()
        logger.info("restored document from trash", extra={"document_id": str(document.id)})

    def purge_document(self, *, document_id: UUID, tenant_id: UUID) -> None:
        document = self.documents.get_for_tenant(document_id, tenant_id, trash="trashed")
        if document is None:
            raise ApplicationError(
                "Document not found in trash",
                status_code=404,
                code="document_not_found",
            )

        doc_key = and_(
            Document.id == document.id,
            Document.created_at == document.created_at,
        )
        page_storage_ids = list(
            self.session.scalars(
                select(DocumentPage.storage_object_id).where(
                    DocumentPage.document_id == document.id,
                    DocumentPage.document_created_at == document.created_at,
                    DocumentPage.storage_object_id.isnot(None),
                )
            )
        )
        storage_ids = {document.storage_object_id, *page_storage_ids}
        storage_objects = self.storage_objects.list_by_ids(list(storage_ids))

        self.session.execute(
            delete(DocumentRelation).where(
                DocumentRelation.tenant_id == tenant_id,
                or_(
                    and_(
                        DocumentRelation.from_document_id == document.id,
                        DocumentRelation.from_document_created_at == document.created_at,
                    ),
                    and_(
                        DocumentRelation.to_document_id == document.id,
                        DocumentRelation.to_document_created_at == document.created_at,
                    ),
                ),
            )
        )
        self.session.execute(
            delete(ExtractedField).where(
                ExtractedField.document_id == document.id,
                ExtractedField.document_created_at == document.created_at,
            )
        )
        self.session.execute(
            delete(OcrResult).where(
                OcrResult.document_id == document.id,
                OcrResult.document_created_at == document.created_at,
            )
        )
        self.session.execute(
            delete(ProcessingEvent).where(
                ProcessingEvent.document_id == document.id,
                ProcessingEvent.document_created_at == document.created_at,
            )
        )
        self.session.execute(
            delete(ProcessingJob).where(
                ProcessingJob.document_id == document.id,
                ProcessingJob.document_created_at == document.created_at,
            )
        )
        self.session.execute(
            delete(DocumentPage).where(
                DocumentPage.document_id == document.id,
                DocumentPage.document_created_at == document.created_at,
            )
        )
        self.session.execute(delete(Document).where(doc_key))
        for storage_object in storage_objects:
            self.storage_objects.delete(storage_object)
        self.session.commit()

        for storage_object in storage_objects:
            self.storage.delete_object(
                bucket=storage_object.bucket,
                object_key=storage_object.object_key,
            )
        logger.info("purged document", extra={"document_id": str(document.id)})

    def purge_all_trash(self, *, tenant_id: UUID) -> int:
        purged = 0
        while True:
            items, _ = self.documents.list_trashed_for_tenant(
                tenant_id=tenant_id,
                limit=50,
                offset=0,
            )
            if not items:
                break
            for document in items:
                self.purge_document(document_id=document.id, tenant_id=tenant_id)
                purged += 1
        return purged

    def delete_document(self, *, document_id: UUID, tenant_id: UUID) -> None:
        """Soft-delete: move document to trash."""
        self.move_document_to_trash(document_id=document_id, tenant_id=tenant_id)
