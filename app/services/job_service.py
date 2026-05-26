from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.errors import ApplicationError
from app.models.document import Document
from app.models.enums import DocumentStatus, ProcessingJobStatus, ProcessingJobType
from app.models.processing_job import ProcessingJob
from app.repositories.documents import DocumentRepository
from app.repositories.events import ProcessingEventRepository
from app.repositories.jobs import ProcessingJobRepository


class JobService:
    def __init__(self, session: Session):
        self.session = session
        self.documents = DocumentRepository(session)
        self.jobs = ProcessingJobRepository(session)
        self.events = ProcessingEventRepository(session)

    def create_reprocess_job(
        self,
        *,
        document_id: UUID,
        tenant_id: UUID,
        reason: str | None,
        enqueue_ocr_job: Callable[[str], object],
    ) -> tuple[ProcessingJob, Document]:
        document = self.documents.get_for_tenant(document_id, tenant_id)
        if document is None:
            raise ApplicationError("Document not found", status_code=404, code="document_not_found")

        now = datetime.now(UTC)
        document.status = DocumentStatus.QUEUED.value
        document.updated_at = now
        job = ProcessingJob(
            id=uuid4(),
            document_id=document.id,
            document_created_at=document.created_at,
            job_type=ProcessingJobType.OCR.value,
            status=ProcessingJobStatus.QUEUED.value,
            created_at=now,
            updated_at=now,
        )
        self.jobs.add(job)
        self.events.add(
            document_id=document.id,
            document_created_at=document.created_at,
            job_id=job.id,
            event_type="document.reprocess_queued",
            message="Document queued for OCR reprocessing",
            payload={"reason": reason},
        )
        self.session.flush()
        async_result = enqueue_ocr_job(str(job.id))
        self.jobs.set_celery_task_id(job, getattr(async_result, "id", None))
        self.session.commit()
        return job, document
