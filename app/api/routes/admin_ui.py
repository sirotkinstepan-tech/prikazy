from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import DbSessionDep, SettingsDep, WebAdminDep
from app.core.document_sections import document_sections_for_ui, section_label_for
from app.core.errors import ApplicationError
from app.core.section_permissions import (
    default_employee_section_access,
    empty_employee_section_access,
    section_access_options_for_ui,
)
from app.repositories.document_relations import DocumentRelationRepository
from app.repositories.documents import DocumentRepository
from app.repositories.events import ProcessingEventRepository
from app.repositories.ocr_results import OcrResultRepository
from app.repositories.search import SearchRepository
from app.models.enums import SectionAccessLevel, UserRole
from app.repositories.users import UserRepository
from app.security.csrf import verify_csrf_form
from app.services.document_link_service import CreateDocumentLinkCommand, DocumentLinkService
from app.services.user_service import CreateUserCommand, UpdateUserCommand, UserService
from app.services.document_service import DocumentService, UploadDocumentCommand
from app.services.job_service import JobService
from app.services.storage_service import ObjectStorageService
from app.core.section_permissions import section_access_label
from app.web.helpers import format_date, format_size, role_label, status_class, status_label, user_error_label
from app.web.template_context import web_template_context
from app.workers.tasks import process_ocr_job

router = APIRouter(prefix="/admin", tags=["admin"])

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals.update(
    status_label=status_label,
    status_class=status_class,
    format_date=format_date,
    format_size=format_size,
    role_label=role_label,
    user_error_label=user_error_label,
    section_label=section_label_for,
)


@router.get("/")
def admin_dashboard(request: Request, user: WebAdminDep, session: DbSessionDep):
    repository = DocumentRepository(session)
    items, total = repository.list_for_tenant(tenant_id=user.tenant_id, limit=10, offset=0)
    for item in items:
        item.latest_job = repository.latest_job_for_document(item)
    failed, failed_total = repository.list_for_tenant(
        tenant_id=user.tenant_id, status="failed", limit=5, offset=0
    )
    queued, queued_total = repository.list_for_tenant(
        tenant_id=user.tenant_id, status="queued", limit=1, offset=0
    )
    processing, processing_total = repository.list_for_tenant(
        tenant_id=user.tenant_id, status="processing", limit=1, offset=0
    )
    users = UserRepository(session).list_for_tenant(user.tenant_id)
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            **web_template_context(request),
            "user": user,
            "recent_documents": items,
            "total_documents": total,
            "failed_documents": failed,
            "failed_total": failed_total,
            "pending_total": queued_total + processing_total,
            "users_count": len(users),
        },
    )


@router.get("/documents")
def admin_documents(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    doc_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    counterparty_name: str | None = None,
    document_date_from: date | None = None,
    document_date_to: date | None = None,
    page: int = Query(default=1, ge=1),
):
    limit = 30
    offset = (page - 1) * limit
    repository = DocumentRepository(session)
    items, total = repository.list_for_tenant(
        tenant_id=user.tenant_id,
        doc_type=doc_type,
        status=status_filter,
        counterparty_name=counterparty_name,
        document_date_from=document_date_from,
        document_date_to=document_date_to,
        limit=limit,
        offset=offset,
    )
    for item in items:
        item.latest_job = repository.latest_job_for_document(item)
    total_pages = max(1, (total + limit - 1) // limit)
    trash_count = repository.count_trashed_for_tenant(user.tenant_id)
    return templates.TemplateResponse(
        request,
        "admin/documents.html",
        {
            **web_template_context(request),
            "user": user,
            "documents": items,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "trash_count": trash_count,
            "trash_view": False,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "filters": {
                "doc_type": doc_type or "",
                "status": status_filter or "",
                "counterparty_name": counterparty_name or "",
                "document_date_from": document_date_from,
                "document_date_to": document_date_to,
            },
        },
    )


@router.get("/documents/trash")
def admin_documents_trash(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    page: int = Query(default=1, ge=1),
):
    limit = 30
    offset = (page - 1) * limit
    repository = DocumentRepository(session)
    items, total = repository.list_trashed_for_tenant(
        tenant_id=user.tenant_id,
        limit=limit,
        offset=offset,
    )
    for item in items:
        item.latest_job = repository.latest_job_for_document(item)
    total_pages = max(1, (total + limit - 1) // limit)
    trash_count = total
    return templates.TemplateResponse(
        request,
        "admin/documents.html",
        {
            **web_template_context(request),
            "user": user,
            "documents": items,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "trash_count": trash_count,
            "trash_view": True,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "filters": {},
        },
    )


@router.post("/documents/{document_id}/delete")
def admin_document_delete(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    service = DocumentService(
        session=session,
        settings=settings,
        storage=ObjectStorageService(settings),
    )
    try:
        service.move_document_to_trash(document_id=document_id, tenant_id=user.tenant_id)
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/documents?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url="/admin/documents?success=trashed",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/trash/{document_id}/restore")
def admin_document_restore(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    service = DocumentService(
        session=session,
        settings=settings,
        storage=ObjectStorageService(settings),
    )
    try:
        service.restore_document_from_trash(document_id=document_id, tenant_id=user.tenant_id)
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/documents/trash?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url="/admin/documents/trash?success=restored",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/trash/{document_id}/purge")
def admin_document_purge(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    settings: SettingsDep,
    document_id: UUID,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    service = DocumentService(
        session=session,
        settings=settings,
        storage=ObjectStorageService(settings),
    )
    try:
        service.purge_document(document_id=document_id, tenant_id=user.tenant_id)
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/documents/trash?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url="/admin/documents/trash?success=purged",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/trash/empty")
def admin_trash_empty(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    settings: SettingsDep,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    service = DocumentService(
        session=session,
        settings=settings,
        storage=ObjectStorageService(settings),
    )
    purged = service.purge_all_trash(tenant_id=user.tenant_id)
    return RedirectResponse(
        url=f"/admin/documents/trash?success=emptied&count={purged}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/documents/{document_id}")
def admin_document_detail(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    document_id: UUID,
):
    repository = DocumentRepository(session)
    document = repository.get_for_tenant(document_id, user.tenant_id, trash="any")
    if document is None:
        raise ApplicationError("Document not found", status_code=404, code="document_not_found")
    document.latest_job = repository.latest_job_for_document(document)
    in_trash = document.archived_at is not None
    ocr_repository = OcrResultRepository(session)
    ocr_result = ocr_repository.latest_for_document(document.id, document.created_at)
    extracted_fields = ocr_repository.fields_for_result(ocr_result) if ocr_result else []
    events = ProcessingEventRepository(session).list_for_document(
        document_id=document.id,
        document_created_at=document.created_at,
    )
    related_documents = DocumentLinkService(session).list_related(
        tenant_id=user.tenant_id,
        document_id=document.id,
        document_created_at=document.created_at,
    )
    link_error = request.query_params.get("link_error")
    link_success = request.query_params.get("link_success")
    return templates.TemplateResponse(
        request,
        "admin/document_detail.html",
        {
            **web_template_context(request),
            "user": user,
            "document": document,
            "ocr_result": ocr_result,
            "extracted_fields": extracted_fields,
            "events": events,
            "related_documents": related_documents,
            "link_error": link_error,
            "link_success": link_success,
            "in_trash": in_trash,
        },
    )


@router.post("/documents/{document_id}/links")
def admin_document_add_link(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    document_id: UUID,
    target_document_id: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    link_label: Annotated[str | None, Form()] = None,
):
    verify_csrf_form(request, csrf_token)
    try:
        target_id = UUID(target_document_id.strip())
    except ValueError:
        return RedirectResponse(
            url=f"/admin/documents/{document_id}?link_error=invalid_target",
            status_code=status.HTTP_303_SEE_OTHER,
        )
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
            url=f"/admin/documents/{document_id}?link_error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/admin/documents/{document_id}?link_success=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/{document_id}/links/{relation_id}/delete")
def admin_document_remove_link(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    document_id: UUID,
    relation_id: UUID,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    try:
        DocumentLinkService(session).remove_link(
            relation_id=relation_id,
            tenant_id=user.tenant_id,
        )
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/documents/{document_id}?link_error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/admin/documents/{document_id}?link_success=removed",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/{document_id}/reprocess")
def admin_reprocess(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    document_id: UUID,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    service = JobService(session)
    service.create_reprocess_job(
        document_id=document_id,
        tenant_id=user.tenant_id,
        reason="Manual reprocess from admin UI",
        enqueue_ocr_job=process_ocr_job.delay,
    )
    return RedirectResponse(
        url=f"/admin/documents/{document_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/upload")
def admin_upload_page(request: Request, user: WebAdminDep):
    return templates.TemplateResponse(
        request,
        "admin/upload.html",
        web_template_context(request, user=user, success=request.query_params.get("success")),
    )


@router.post("/upload")
async def admin_upload(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    csrf_token: Annotated[str, Form()],
    doc_type: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    document_date: Annotated[date | None, Form()] = None,
    counterparty_name: Annotated[str | None, Form()] = None,
):
    verify_csrf_form(request, csrf_token)
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
            doc_type=doc_type or "prikaz",
            document_date=document_date,
            counterparty_name=counterparty_name,
            title=title.strip() if title else None,
            created_by_user_id=user.id,
        ),
        enqueue_ocr_job=process_ocr_job.delay,
    )
    return RedirectResponse(
        url="/admin/upload?success=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/search")
def admin_search(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    q: str = "",
    doc_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
):
    results = []
    total = 0
    if q.strip():
        repository = SearchRepository(session)
        results, total = repository.search(
            tenant_id=user.tenant_id,
            query=q.strip(),
            doc_type=doc_type,
            status=status_filter,
            limit=100,
        )
        related_by_doc = DocumentRelationRepository(session).list_related_by_document_ids(
            tenant_id=user.tenant_id,
            document_ids=[row["document_id"] for row in results],
        )
        for row in results:
            row["related_documents"] = related_by_doc.get(row["document_id"], [])
    return templates.TemplateResponse(
        request,
        "admin/search.html",
        {
            **web_template_context(request),
            "user": user,
            "q": q,
            "results": results,
            "total": total,
            "doc_type": doc_type or "",
            "status_filter": status_filter or "",
        },
    )


@router.get("/users")
def admin_users(request: Request, user: WebAdminDep, session: DbSessionDep):
    users = UserRepository(session).list_for_tenant(user.tenant_id)
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            **web_template_context(request),
            "user": user,
            "users": users,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


def _user_form_context(
    *,
    request: Request,
    user,
    form_user,
    form_action: str,
    form_title: str,
    session,
    error: str | None,
) -> dict:
    if form_user is not None:
        stored = UserService(session).get_section_access_for_user(form_user.id)
        base = empty_employee_section_access()
        section_access_values = {}
        for section in document_sections_for_ui():
            slug = section["slug"]
            level = stored.get(slug, base.get(slug, SectionAccessLevel.NONE))
            section_access_values[slug] = level.value
    else:
        defaults = default_employee_section_access()
        section_access_values = {
            section["slug"]: defaults[section["slug"]].value
            for section in document_sections_for_ui()
        }
    return {
        **web_template_context(request),
        "user": user,
        "form_user": form_user,
        "form_action": form_action,
        "form_title": form_title,
        "error": error,
        "document_sections": document_sections_for_ui(),
        "section_access_options": section_access_options_for_ui(),
        "section_access_values": section_access_values,
        "section_access_label": section_access_label,
    }


@router.get("/users/new")
def admin_user_new(request: Request, user: WebAdminDep, session: DbSessionDep):
    return templates.TemplateResponse(
        request,
        "admin/user_form.html",
        _user_form_context(
            request=request,
            user=user,
            form_user=None,
            form_action="/admin/users",
            form_title="Новый пользователь",
            session=session,
            error=request.query_params.get("error"),
        ),
    )


def _parse_role(role: str) -> UserRole | None:
    try:
        return UserRole(role)
    except ValueError:
        return None


@router.post("/users")
async def admin_user_create(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    full_name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    parsed_role = _parse_role(role)
    if parsed_role is None:
        return RedirectResponse(
            url="/admin/users/new?error=invalid_role",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    form = await request.form()
    section_levels = {
        key.removeprefix("section_access_"): value
        for key, value in form.items()
        if key.startswith("section_access_")
    }
    try:
        section_access = UserService.parse_section_access_from_form(section_levels)
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/users/new?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        UserService(session).create_user(
            CreateUserCommand(
                tenant_id=user.tenant_id,
                email=email,
                password=password,
                full_name=full_name,
                role=parsed_role,
                section_access=section_access if parsed_role == UserRole.EMPLOYEE else None,
            )
        )
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/users/new?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url="/admin/users?success=created",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/users/{user_id}/edit")
def admin_user_edit(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    user_id: UUID,
):
    form_user = UserRepository(session).get_for_tenant(user_id, user.tenant_id)
    if form_user is None:
        raise ApplicationError("Пользователь не найден", status_code=404, code="user_not_found")
    return templates.TemplateResponse(
        request,
        "admin/user_form.html",
        _user_form_context(
            request=request,
            user=user,
            form_user=form_user,
            form_action=f"/admin/users/{user_id}",
            form_title="Редактирование пользователя",
            session=session,
            error=request.query_params.get("error"),
        ),
    )


@router.post("/users/{user_id}")
async def admin_user_update(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    user_id: UUID,
    email: Annotated[str, Form()],
    full_name: Annotated[str, Form()],
    role: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    is_active: Annotated[str | None, Form()] = None,
    password: Annotated[str | None, Form()] = None,
):
    verify_csrf_form(request, csrf_token)
    parsed_role = _parse_role(role)
    if parsed_role is None:
        return RedirectResponse(
            url=f"/admin/users/{user_id}/edit?error=invalid_role",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    form = await request.form()
    section_levels = {
        key.removeprefix("section_access_"): value
        for key, value in form.items()
        if key.startswith("section_access_")
    }
    try:
        section_access = UserService.parse_section_access_from_form(section_levels)
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/users/{user_id}/edit?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        UserService(session).update_user(
            UpdateUserCommand(
                user_id=user_id,
                tenant_id=user.tenant_id,
                email=email,
                full_name=full_name,
                role=parsed_role,
                is_active=is_active == "on",
                password=password.strip() if password and password.strip() else None,
                section_access=section_access,
            ),
            acting_user_id=user.id,
        )
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/users/{user_id}/edit?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url="/admin/users?success=updated",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/users/{user_id}/toggle-active")
def admin_user_toggle_active(
    request: Request,
    user: WebAdminDep,
    session: DbSessionDep,
    user_id: UUID,
    csrf_token: Annotated[str, Form()],
):
    verify_csrf_form(request, csrf_token)
    try:
        UserService(session).toggle_active(
            user_id=user_id,
            tenant_id=user.tenant_id,
            acting_user_id=user.id,
        )
    except ApplicationError as exc:
        return RedirectResponse(
            url=f"/admin/users?error={exc.code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url="/admin/users?success=toggled",
        status_code=status.HTTP_303_SEE_OTHER,
    )
