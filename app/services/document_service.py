import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.document_sections import validate_doc_type
from app.core.errors import ApplicationError
from app.models.document import Document
from app.models.enums import DocumentStatus, ProcessingJobStatus, ProcessingJobType
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
