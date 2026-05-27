from uuid import UUID

from fastapi import HTTPException, status

from app.auth.service import AuthenticatedUser
from app.core.document_sections import validate_doc_type
from app.core.errors import ApplicationError
from app.web.portal_context import merge_doc_types_filter
from app.web.section_access import (
    require_section_download,
    require_section_upload,
    require_section_view,
)


def ensure_tenant_id(user: AuthenticatedUser, tenant_id: UUID | None) -> UUID:
    if tenant_id is not None and tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant access denied",
        )
    return user.tenant_id


def resolve_api_doc_types(
    user: AuthenticatedUser,
    *,
    doc_type: str | None,
    doc_types: list[str] | None,
) -> list[str] | None:
    from app.core.document_sections import resolve_doc_type_filters

    resolved = resolve_doc_type_filters(doc_type=doc_type, doc_types=doc_types)
    return merge_doc_types_filter(user, "all", resolved)


def require_api_section_view(user: AuthenticatedUser, doc_type: str | None) -> None:
    if doc_type:
        validate_doc_type(doc_type)
    require_section_view(user, doc_type)


def require_api_section_upload(user: AuthenticatedUser, doc_type: str) -> None:
    validate_doc_type(doc_type)
    require_section_upload(user, doc_type)


def require_api_section_download(user: AuthenticatedUser, doc_type: str | None) -> None:
    require_section_download(user, doc_type)


def require_document_access(
    user: AuthenticatedUser,
    *,
    doc_type: str | None,
    for_download: bool = False,
) -> None:
    if for_download:
        require_api_section_download(user, doc_type)
    else:
        require_api_section_view(user, doc_type)


def document_not_found() -> ApplicationError:
    return ApplicationError("Document not found", status_code=404, code="document_not_found")
