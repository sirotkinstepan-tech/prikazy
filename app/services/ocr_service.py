import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.enums import DocumentStatus, ProcessingJobStatus
from app.models.extracted_field import ExtractedField
from app.models.ocr_result import OcrResult
from app.repositories.events import ProcessingEventRepository
from app.repositories.jobs import ProcessingJobRepository
from app.repositories.ocr_results import OcrResultRepository
from app.services.ocr_provider import process_document_content
from app.services.storage_service import ObjectStorageService

logger = logging.getLogger(__name__)


class OcrProcessingService:
    def __init__(self, session: Session | None = None):
        self.settings = get_settings()
        self._external_session = session

    def process_job(self, job_id: str) -> None:
        if self._external_session is not None:
            self._process_job(UUID(job_id), self._external_session)
            return

        with SessionLocal() as session:
            self._process_job(UUID(job_id), session)

    def _process_job(self, job_id: UUID, session: Session) -> None:
        jobs = ProcessingJobRepository(session)
        events = ProcessingEventRepository(session)
        ocr_results = OcrResultRepository(session)

        job = jobs.get_for_update(job_id)
        if job is None:
            logger.warning("ocr job not found", extra={"job_id": str(job_id)})
            return
        if job.status not in {ProcessingJobStatus.QUEUED.value, ProcessingJobStatus.FAILED.value}:
            logger.info(
                "ocr job skipped because status is not processable",
                extra={"job_id": str(job_id)},
            )
            return

        document = session.get(Document, (job.document_id, job.document_created_at))
        if document is None:
            jobs.mark_failed(job, code="document_not_found", message="Document not found")
            session.commit()
            return

        try:
            jobs.mark_processing(job)
            document.status = DocumentStatus.PROCESSING.value
            document.updated_at = datetime.now(UTC)
            events.add(
                document_id=document.id,
                document_created_at=document.created_at,
                job_id=job.id,
                event_type="ocr.processing_started",
                message="OCR processing started",
            )
            session.flush()

            storage = ObjectStorageService(self.settings)
            content = storage.download_bytes(
                bucket=document.storage_object.bucket,
                object_key=document.storage_object.object_key,
            )
            provider_result = process_document_content(
                content=content,
                mime_type=document.mime_type,
                filename=document.source_filename,
                ocr_provider_name=self.settings.default_ocr_provider,
                tesseract_languages=self.settings.ocr_tesseract_languages,
                tesseract_dpi_scale=self.settings.ocr_tesseract_dpi_scale,
            )
            processed_at = datetime.now(UTC)
            ocr_result = OcrResult(
                id=uuid4(),
                processed_at=processed_at,
                document_id=document.id,
                document_created_at=document.created_at,
                job_id=job.id,
                provider=provider_result.provider,
                language=provider_result.language,
                full_text=provider_result.full_text,
                confidence=provider_result.confidence,
                layout_json=provider_result.layout_json,
                page_data=provider_result.page_data,
                created_at=processed_at,
            )
            ocr_results.add(ocr_result)
            self._ensure_first_page(session, document, processed_at)
            for field in provider_result.extracted_fields:
                ocr_results.add_extracted_field(
                    ExtractedField(
                        id=uuid4(),
                        document_id=document.id,
                        document_created_at=document.created_at,
                        ocr_result_id=ocr_result.id,
                        ocr_result_processed_at=ocr_result.processed_at,
                        field_name=field.field_name,
                        field_value=field.field_value,
                        field_type=field.field_type,
                        confidence=field.confidence,
                        source_json=field.source_json,
                        created_at=processed_at,
                    )
                )

            document.status = DocumentStatus.PROCESSED.value
            document.updated_at = datetime.now(UTC)
            jobs.mark_succeeded(job)
            events.add(
                document_id=document.id,
                document_created_at=document.created_at,
                job_id=job.id,
                event_type="ocr.processed",
                message="OCR processing completed",
                payload={
                    "provider": provider_result.provider,
                    "confidence": str(provider_result.confidence),
                },
            )
            session.commit()
            logger.info(
                "ocr job processed",
                extra={"job_id": str(job.id), "document_id": str(document.id)},
            )
        except Exception as exc:
            session.rollback()
            self._mark_failed_after_exception(job_id, str(exc))
            raise

    def _ensure_first_page(
        self,
        session: Session,
        document: Document,
        created_at: datetime,
    ) -> None:
        from sqlalchemy import select

        existing_page = session.scalars(
            select(DocumentPage)
            .where(
                DocumentPage.document_id == document.id,
                DocumentPage.document_created_at == document.created_at,
                DocumentPage.page_number == 1,
            )
            .limit(1)
        ).first()
        if existing_page is not None:
            return
        session.add(
            DocumentPage(
                id=uuid4(),
                document_id=document.id,
                document_created_at=document.created_at,
                page_number=1,
                created_at=created_at,
            )
        )

    def _mark_failed_after_exception(self, job_id: UUID, message: str) -> None:
        with SessionLocal() as session:
            jobs = ProcessingJobRepository(session)
            events = ProcessingEventRepository(session)
            job = jobs.get_for_update(job_id)
            if job is None:
                return
            jobs.mark_failed(job, code="ocr_processing_failed", message=message)
            document = session.get(Document, (job.document_id, job.document_created_at))
            if document is not None:
                document.status = DocumentStatus.FAILED.value
                document.updated_at = datetime.now(UTC)
                events.add(
                    document_id=document.id,
                    document_created_at=document.created_at,
                    job_id=job.id,
                    event_type="ocr.failed",
                    message=message,
                )
            session.commit()
