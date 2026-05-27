from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.api.dependencies import DbSessionDep, SettingsDep, WebUserDep
from app.core.document_sections import (
    document_sections_for_ui,
    resolve_doc_type_filters,
    section_label_for,
    validate_doc_type,
)
from app.core.errors import ApplicationError
from app.models.enums import DocumentType
from app.core.section_permissions import level_can_download, level_can_upload
from app.repositories.document_relations import DocumentRelationRepository
from app.repositories.documents import DocumentRepository
from app.repositories.ocr_results import OcrResultRepository
from app.repositories.search import SearchRepository
from app.security.csrf import verify_csrf_form
from app.services.document_link_service import CreateDocumentLinkCommand, DocumentLinkService
from app.services.document_service import DocumentService, UploadDocumentCommand
from app.web.portal_context import merge_doc_types_filter, portal_template_context
from app.web.template_context import web_template_context
from app.web.section_access import (
    can_manage_document_links,
    require_section_download,
    require_section_manage_links,
    require_section_upload,
    require_section_view,
)
from app.services.storage_service import ObjectStorageService
from app.web.file_responses import build_document_file_response
from app.web.helpers import format_date, format_size, status_class, status_label
from app.workers.tasks import process_ocr_job

router = APIRouter(prefix="/portal", tags=["portal"])

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(
    status_label=status_label,
    status_class=status_class,
    format_date=format_date,
    format_size=format_size,
    section_label=section_label_for,
    document_sections=document_sections_for_ui,
)


def _resolve_section_filter(section: str | None) -> list[str] | None:
    if not section or section == "all":
        return None
    return resolve_doc_type_filters(doc_type=section, doc_types=None)


def _portal_ctx(request: Request, user: WebUserDep) -> dict:
    return {**portal_template_context(user), **web_template_context(request)}


@router.get("/")
def portal_home(request: Request, user: WebUserDep, session: DbSessionDep):
    repository = DocumentRepository(session)
    doc_types = merge_doc_types_filter(user, "all", None)
    items, total = repository.list_for_tenant(
        tenant_id=user.tenant_id,
        doc_types=doc_types,
        limit=5,
        offset=0,
    )
    processed, _ = repository.list_for_tenant(
        tenant_id=user.tenant_id,
        doc_types=doc_types,
        status="processed",
        limit=1,
        offset=0,
    )
    return templates.TemplateResponse(
        request,
        "portal/index.html",
        {
            "user": user,
            "recent_documents": items,
            "total_documents": total,
            "has_processed": len(processed) > 0,
            "current_section": "all",
            **_portal_ctx(request, user),
        },
    )


@router.get("/upload")
def upload_page(
    request: Request,
    user: WebUserDep,
    section: str | None = Query(default=None),
):
    ctx = _portal_ctx(request, user)
    if not ctx["can_upload_any"]:
        return RedirectResponse(url="/portal/?error=section_upload_denied", status_code=status.HTTP_303_SEE_OTHER)
    upload_sections = [
        s
        for s in ctx["portal_sections"]
        if user.is_admin or level_can_upload(user.section_access.get(s["slug"]))
    ]
    selected_section = upload_sections[0]["slug"] if upload_sections else DocumentType.PRIKAZ.value
    if section and section != "all":
        selected_section = validate_doc_type(section)
    require_section_upload(user, selected_section)
    return templates.TemplateResponse(
        request,
        "portal/upload.html",
        {
            "user": user,
            "success": request.query_params.get("success"),
            "current_section": selected_section,
            "upload_sections": upload_sections,
            **_portal_ctx(request, user),
        },
    )


@router.post("/upload")
async def upload_document(
    request: Request,
    user: WebUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    title: Annotated[str | None, Form()] = None,
    document_date: Annotated[date | None, Form()] = None,
    counterparty_name: Annotated[str | None, Form()] = None,
):
    verify_csrf_form(request, csrf_token)
    validated_doc_type = validate_doc_type(doc_type)
    require_section_upload(user, validated_doc_type)
    content = await file.read()
    service = DocumentService(
        session=session,
        settings=settings,
        storage=ObjectStorageService(settings),
    )
    service.upload_document(
        UploadDocumentCommand(
            tenant_id=user.tenant_id,
            filename=file.filename or "document",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            doc_type=validated_doc_type,
            document_date=document_date,
            counterparty_name=counterparty_name.strip() if counterparty_name else None,
            title=title.strip() if title else None,
        ),
        enqueue_ocr_job=process_ocr_job.delay,
    )
    return RedirectResponse(
        url=f"/portal/upload?success=1&section={validated_doc_type}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/documents")
def documents_list(
    request: Request,
    user: WebUserDep,
    session: DbSessionDep,
    q: str | None = None,
    section: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
):
    limit = 20
    offset = (page - 1) * limit
    doc_types = merge_doc_types_filter(user, section, _resolve_section_filter(section))
    if section and section != "all":
        require_section_view(user, section)
    repository = DocumentRepository(session)
    items, total = repository.list_for_tenant(
        tenant_id=user.tenant_id,
        doc_types=doc_types,
        status=status_filter,
        text_query=q,
        limit=limit,
        offset=offset,
    )
    for item in items:
        item.latest_job = repository.latest_job_for_document(item)
    total_pages = max(1, (total + limit - 1) // limit)
    return templates.TemplateResponse(
        request,
        "portal/documents.html",
        {
            "user": user,
            "documents": items,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "q": q or "",
            "status_filter": status_filter or "",
            "current_section": section or "all",
            **_portal_ctx(request, user),
        },
    )


@router.get("/documents/{document_id}")
def document_detail(
    request: Request,
    user: WebUserDep,
    session: DbSessionDep,
    document_id: UUID,
):
    repository = DocumentRepository(session)
    document = repository.get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")
    section_level = require_section_view(user, document.doc_type)
    document.latest_job = repository.latest_job_for_document(document)
    ocr_repository = OcrResultRepository(session)
    ocr_result = ocr_repository.latest_for_document(document.id, document.created_at)
    extracted_fields = ocr_repository.fields_for_result(ocr_result) if ocr_result else []
    mime = (document.mime_type or "").lower()
    preview_mode = "none"
    if mime == "application/pdf":
        preview_mode = "pdf"
    elif mime.startswith("image/"):
        preview_mode = "image"

    related_documents = DocumentLinkService(session).list_related(
        tenant_id=user.tenant_id,
        document_id=document.id,
        document_created_at=document.created_at,
    )
    return templates.TemplateResponse(
        request,
        "portal/document_detail.html",
        {
            "user": user,
            "document": document,
            "ocr_result": ocr_result,
            "extracted_fields": extracted_fields,
            "preview_mode": preview_mode,
            "current_section": document.doc_type or "all",
            "related_documents": related_documents,
            "can_download": level_can_download(section_level),
            "can_manage_links": can_manage_document_links(user, document.doc_type),
            "link_error": request.query_params.get("link_error"),
            "link_success": request.query_params.get("link_success"),
            **_portal_ctx(request, user),
        },
    )


@router.post("/documents/{document_id}/links")
def portal_document_add_link(
    request: Request,
    user: WebUserDep,
    session: DbSessionDep,
    document_id: UUID,
    target_document_id: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    link_label: Annotated[str | None, Form()] = None,
):
    verify_csrf_form(request, csrf_token)
    repository = DocumentRepository(session)
    source = repository.get_for_tenant(document_id, user.tenant_id)
    if source is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")
    require_section_view(user, source.doc_type)
    try:
        target_id = UUID(target_document_id.strip())
    except ValueError:
        return RedirectResponse(
            url=f"/portal/documents/{document_id}?link_error=invalid_target",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    target = repository.get_for_tenant(target_id, user.tenant_id)
    if target is None:
        return RedirectResponse(
            url=f"/portal/documents/{document_id}?link_error=document_not_found",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    require_section_manage_links(user, target.doc_type)
    try:
        DocumentLinkService(session).create_link(
            CreateDocumentLinkCommand(
                tenant_id=user.tenant_id,
                from_document_id=document_id,
                to_document_id=target_id,
                link_label=link_label,
                created_by_user_id=user.id,
            )
        )
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/portal/documents/{document_id}?link_error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/portal/documents/{document_id}?link_success=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/{document_id}/links/{relation_id}/delete")
def portal_document_remove_link(
    request: Request,
    user: WebUserDep,
    session: DbSessionDep,
    document_id: UUID,
    relation_id: UUID,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    repository = DocumentRepository(session)
    source = repository.get_for_tenant(document_id, user.tenant_id)
    if source is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")
    require_section_manage_links(user, source.doc_type)

    link_service = DocumentLinkService(session)
    relation = link_service.relations.get(relation_id, user.tenant_id)
    if relation is None:
        return RedirectResponse(
            url=f"/portal/documents/{document_id}?link_error=link_not_found",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    is_connected = (
        relation.from_document_id == source.id
        and relation.from_document_created_at == source.created_at
    ) or (
        relation.to_document_id == source.id
        and relation.to_document_created_at == source.created_at
    )
    if not is_connected:
        return RedirectResponse(
            url=f"/portal/documents/{document_id}?link_error=link_not_found",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    other_id = (
        relation.to_document_id
        if relation.from_document_id == source.id
        else relation.from_document_id
    )
    other = repository.get_for_tenant(other_id, user.tenant_id)
    if other is not None:
        require_section_manage_links(user, other.doc_type)

    try:
        link_service.remove_link(relation_id=relation_id, tenant_id=user.tenant_id)
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/portal/documents/{document_id}?link_error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/portal/documents/{document_id}?link_success=removed",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/documents/{document_id}/download")
def portal_download_document(
    user: WebUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
) -> Response:
    document = DocumentRepository(session).get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")
    require_section_download(user, document.doc_type)
    return build_document_file_response(
        session,
        settings,
        document_id=document_id,
        tenant_id=user.tenant_id,
        disposition="attachment",
    )


@router.get("/documents/{document_id}/file")
def portal_document_file(
    user: WebUserDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
    disposition: Literal["inline", "attachment"] = Query(default="inline"),
) -> Response:
    document = DocumentRepository(session).get_for_tenant(document_id, user.tenant_id)
    if document is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")
    if disposition == "attachment":
        require_section_download(user, document.doc_type)
    else:
        require_section_view(user, document.doc_type)
    return build_document_file_response(
        session,
        settings,
        document_id=document_id,
        tenant_id=user.tenant_id,
        disposition=disposition,
    )


@router.get("/search")
def search_page(
    request: Request,
    user: WebUserDep,
    session: DbSessionDep,
    q: str = "",
    section: str | None = Query(default=None),
):
    results = []
    total = 0
    if section and section != "all":
        require_section_view(user, section)
    doc_types = merge_doc_types_filter(user, section, _resolve_section_filter(section))
    if q.strip():
        repository = SearchRepository(session)
        results, total = repository.search(
            tenant_id=user.tenant_id,
            query=q.strip(),
            doc_types=doc_types,
            limit=50,
        )
        related_by_doc = DocumentRelationRepository(session).list_related_by_document_ids(
            tenant_id=user.tenant_id,
            document_ids=[row["document_id"] for row in results],
        )
        for row in results:
            row["related_documents"] = related_by_doc.get(row["document_id"], [])
    return templates.TemplateResponse(
        request,
        "portal/search.html",
        {
            "user": user,
            "q": q,
            "results": results,
            "total": total,
            "current_section": section or "all",
            **_portal_ctx(request, user),
        },
    )
