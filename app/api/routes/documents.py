from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.dependencies import DbSessionDep, SettingsDep
from app.core.errors import ApplicationError
from app.repositories.documents import DocumentRepository
from app.repositories.ocr_results import OcrResultRepository
from app.schemas.documents import (
    DocumentListResponse,
    DocumentOcrResponse,
    DocumentRead,
    DocumentUploadResponse,
    ReprocessRequest,
)
from app.services.document_service import DocumentService, UploadDocumentCommand
from app.services.storage_service import ObjectStorageService
from app.workers.tasks import process_ocr_job

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    session: DbSessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    tenant_id: Annotated[UUID, Form()],
    doc_type: Annotated[str | None, Form()] = None,
    document_date: Annotated[date | None, Form()] = None,
    counterparty_name: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    idempotency_key: Annotated[str | None, Form()] = None,
) -> DocumentUploadResponse:
    content = await file.read()
    service = DocumentService(
        session=session,
        settings=settings,
        storage=ObjectStorageService(settings),
    )
    result = service.upload_document(
        UploadDocumentCommand(
            tenant_id=tenant_id,
            filename=file.filename or "document",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            doc_type=doc_type,
            document_date=document_date,
            counterparty_name=counterparty_name,
            title=title,
        ),
        enqueue_ocr_job=process_ocr_job.delay,
    )
    return DocumentUploadResponse(
        document_id=result.document_id,
        created_at=result.document_created_at,
        status=result.status,
        job_id=result.job_id,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    session: DbSessionDep,
    tenant_id: UUID,
    doc_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    document_date_from: date | None = None,
    document_date_to: date | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    counterparty_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    repository = DocumentRepository(session)
    items, total = repository.list_for_tenant(
        tenant_id=tenant_id,
        doc_type=doc_type,
        status=status_filter,
        document_date_from=document_date_from,
        document_date_to=document_date_to,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        counterparty_name=counterparty_name,
        limit=limit,
        offset=offset,
    )
    response_items = []
    for item in items:
        doc = DocumentRead.model_validate(item)
        doc.latest_job = repository.latest_job_for_document(item)
        response_items.append(doc)
    return DocumentListResponse(items=response_items, limit=limit, offset=offset, total=total)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(session: DbSessionDep, document_id: UUID, tenant_id: UUID) -> DocumentRead:
    repository = DocumentRepository(session)
    document = repository.get_for_tenant(document_id, tenant_id)
    if document is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")
    response = DocumentRead.model_validate(document)
    response.latest_job = repository.latest_job_for_document(document)
    return response


@router.post("/{document_id}/reprocess", response_model=DocumentUploadResponse)
def reprocess_document(
    session: DbSessionDep,
    document_id: UUID,
    tenant_id: UUID,
    request: ReprocessRequest | None = None,
) -> DocumentUploadResponse:
    from app.services.job_service import JobService

    service = JobService(session)
    job, document = service.create_reprocess_job(
        document_id=document_id,
        tenant_id=tenant_id,
        reason=request.reason if request else None,
        enqueue_ocr_job=process_ocr_job.delay,
    )
    return DocumentUploadResponse(
        document_id=document.id,
        created_at=document.created_at,
        status=document.status,
        job_id=job.id,
    )


@router.get("/{document_id}/ocr", response_model=DocumentOcrResponse)
def get_document_ocr(
    session: DbSessionDep,
    document_id: UUID,
    tenant_id: UUID,
) -> DocumentOcrResponse:
    document_repository = DocumentRepository(session)
    document = document_repository.get_for_tenant(document_id, tenant_id)
    if document is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")

    ocr_repository = OcrResultRepository(session)
    ocr_result = ocr_repository.latest_for_document(document.id, document.created_at)
    if ocr_result is None:
        return DocumentOcrResponse(ocr_result=None, extracted_fields=[])
    return DocumentOcrResponse(
        ocr_result=ocr_result,
        extracted_fields=ocr_repository.fields_for_result(ocr_result),
    )
