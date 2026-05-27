from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.enums import ProcessingJobStatus
from app.models.processing_job import ProcessingJob


class ProcessingJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, job: ProcessingJob) -> ProcessingJob:
        self.session.add(job)
        return job

    def get(self, job_id: UUID) -> ProcessingJob | None:
        return self.session.get(ProcessingJob, job_id)

    def get_for_update(self, job_id: UUID) -> ProcessingJob | None:
        return self.session.scalars(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        ).first()

    def set_celery_task_id(self, job: ProcessingJob, celery_task_id: str | None) -> None:
        job.celery_task_id = celery_task_id
        job.updated_at = datetime.now(UTC)

    def mark_processing(self, job: ProcessingJob) -> None:
        now = datetime.now(UTC)
        job.status = "processing"
        job.attempt += 1
        job.locked_at = now
        job.started_at = now
        job.updated_at = now

    def mark_succeeded(self, job: ProcessingJob) -> None:
        now = datetime.now(UTC)
        job.status = "succeeded"
        job.finished_at = now
        job.updated_at = now
        job.error_code = None
        job.error_message = None

    def mark_failed(self, job: ProcessingJob, *, code: str, message: str) -> None:
        now = datetime.now(UTC)
        job.status = "failed"
        job.finished_at = now
        job.updated_at = now
        job.error_code = code
        job.error_message = message

    def cancel_queued_for_document(
        self,
        *,
        document_id: UUID,
        document_created_at: datetime,
    ) -> int:
        now = datetime.now(UTC)
        result = self.session.execute(
            update(ProcessingJob)
            .where(
                ProcessingJob.document_id == document_id,
                ProcessingJob.document_created_at == document_created_at,
                ProcessingJob.status == ProcessingJobStatus.QUEUED.value,
            )
            .values(
                status=ProcessingJobStatus.FAILED.value,
                finished_at=now,
                updated_at=now,
                error_code="superseded",
                error_message="Superseded by a newer processing job",
            )
        )
        return result.rowcount or 0
