from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response

from app.api.access import (
    document_not_found,
    ensure_tenant_id,
    require_api_section_download,
    require_api_section_upload,
    require_api_section_view,
    require_document_access,
    resolve_api_doc_types,
)
from app.api.dependencies import CsrfHeaderDep, CurrentUserDep, DbSessionDep, SettingsDep
from app.api.document_urls import attach_document_links
from app.core.document_sections import validate_doc_type
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
from app.web.file_responses import build_document_file_response
from app.workers.tasks import process_ocr_job

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    _csrf: CsrfHeaderDep,
    user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[str, Form()],
    document_date: Annotated[date | None, Form()] = None,
    counterparty_name: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
) -> DocumentUploadResponse:
    validated_doc_type = validate_doc_type(doc_type)
    require_api_section_upload(user, validated_doc_type)
    content = await file.read()
    service = DocumentService(
        session=session,
        settings=settings,
        storage=ObjectStorageService(settings),
    )
    result = service.upload_document(
        UploadDocumentCommand(
            tenant_id=user.tenant_id,
            filename=file.filename or "document",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            doc_type=validated_doc_type,
            document_date=document_date,
            counterparty_name=counterparty_name,
            title=title,
            created_by_user_id=user.id,
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
    user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    tenant_id: UUID | None = None,
    doc_type: str | None = None,
    doc_types: list[str] | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    document_date_from: date | None = None,
    document_date_to: date | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    counterparty_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    ensure_tenant_id(user, tenant_id)
    resolved_doc_types = resolve_api_doc_types(user, doc_type=doc_type, doc_types=doc_types)
    if doc_type:
        require_api_section_view(user, doc_type)
    repository = DocumentRepository(session)
    items, total = repository.list_for_tenant(
        tenant_id=user.tenant_id,
        doc_types=resolved_doc_types,
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
        attach_document_links(doc, settings)
        response_items.append(doc)
    return DocumentListResponse(items=response_items, limit=limit, offset=offset, total=total)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
    tenant_id: UUID | None = None,
) -> DocumentRead:
    ensure_tenant_id(user, tenant_id)
    repository = DocumentRepository(session)
    document = repository.get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise document_not_found()
    require_document_access(user, doc_type=document.doc_type)
    response = DocumentRead.model_validate(document)
    response.latest_job = repository.latest_job_for_document(document)
    return attach_document_links(response, settings)


@router.post("/{document_id}/reprocess", response_model=DocumentUploadResponse)
def reprocess_document(
    _csrf: CsrfHeaderDep,
    user: CurrentUserDep,
    session: DbSessionDep,
    document_id: UUID,
    tenant_id: UUID | None = None,
    request: ReprocessRequest | None = None,
) -> DocumentUploadResponse:
    from app.services.job_service import JobService

    ensure_tenant_id(user, tenant_id)
    repository = DocumentRepository(session)
    document = repository.get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise document_not_found()
    if document.doc_type is None:
        raise ApplicationError("Document section is missing", status_code=400, code="missing_doc_type")
    require_api_section_upload(user, document.doc_type)

    service = JobService(session)
    job, document = service.create_reprocess_job(
        document_id=document_id,
        tenant_id=user.tenant_id,
        reason=request.reason if request else None,
        enqueue_ocr_job=process_ocr_job.delay,
    )
    return DocumentUploadResponse(
        document_id=document.id,
        created_at=document.created_at,
        status=document.status,
        job_id=job.id,
    )


@router.get("/{document_id}/file")
def get_document_file(
    user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
    tenant_id: UUID | None = None,
    disposition: Literal["inline", "attachment"] = Query(default="inline"),
) -> Response:
    ensure_tenant_id(user, tenant_id)
    document = DocumentRepository(session).get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise document_not_found()
    if disposition == "attachment":
        require_api_section_download(user, document.doc_type)
    else:
        require_document_access(user, doc_type=document.doc_type)
    return build_document_file_response(
        session,
        settings,
        document_id=document_id,
        tenant_id=user.tenant_id,
        disposition=disposition,
    )


@router.get("/{document_id}/download")
def download_document(
    user: CurrentUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
    tenant_id: UUID | None = None,
) -> Response:
    ensure_tenant_id(user, tenant_id)
    document = DocumentRepository(session).get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise document_not_found()
    require_api_section_download(user, document.doc_type)
    return build_document_file_response(
        session,
        settings,
        document_id=document_id,
        tenant_id=user.tenant_id,
        disposition="attachment",
    )


@router.get("/{document_id}/ocr", response_model=DocumentOcrResponse)
def get_document_ocr(
    user: CurrentUserDep,
    session: DbSessionDep,
    document_id: UUID,
    tenant_id: UUID | None = None,
) -> DocumentOcrResponse:
    ensure_tenant_id(user, tenant_id)
    document_repository = DocumentRepository(session)
    document = document_repository.get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise document_not_found()
    require_document_access(user, doc_type=document.doc_type)

    ocr_repository = OcrResultRepository(session)
    ocr_result = ocr_repository.latest_for_document(document.id, document.created_at)
    if ocr_result is None:
        return DocumentOcrResponse(ocr_result=None, extracted_fields=[])
    return DocumentOcrResponse(
        ocr_result=ocr_result,
        extracted_fields=ocr_repository.fields_for_result(ocr_result),
    )
