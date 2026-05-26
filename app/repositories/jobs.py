from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

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
