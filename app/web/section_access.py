from typing import Literal

from app.auth.service import AuthenticatedUser
from app.core.errors import ApplicationError
from app.core.section_permissions import (
    access_for_doc_type,
    allowed_doc_types_for_view,
    level_can_download,
    level_can_manage_document_links,
    level_can_upload,
    level_can_use_ai,
    level_has_unlimited_ai,
    level_can_view,
)
from app.models.enums import SectionAccessLevel, UserRole

AiAccessMode = Literal["none", "limited", "unlimited"]


def user_allowed_doc_types(user: AuthenticatedUser) -> list[str] | None:
    """None = все разделы (админ)."""
    if user.role == UserRole.ADMIN:
        return None
    allowed = allowed_doc_types_for_view(user.section_access)
    return allowed or []


def require_section_view(user: AuthenticatedUser, doc_type: str | None) -> SectionAccessLevel:
    level = access_for_doc_type(user.section_access, doc_type)
    if user.role == UserRole.ADMIN:
        return SectionAccessLevel.FULL
    if not level_can_view(level):
        raise ApplicationError(
            "Нет доступа к этому разделу",
            status_code=403,
            code="section_access_denied",
        )
    return level


def require_section_upload(user: AuthenticatedUser, doc_type: str) -> None:
    level = require_section_view(user, doc_type)
    if not level_can_upload(level):
        raise ApplicationError(
            "Нет права на загрузку в этот раздел",
            status_code=403,
            code="section_upload_denied",
        )


def require_section_download(user: AuthenticatedUser, doc_type: str | None) -> None:
    level = require_section_view(user, doc_type)
    if not level_can_download(level):
        raise ApplicationError(
            "Нет права на скачивание из этого раздела",
            status_code=403,
            code="section_download_denied",
        )


def user_can_upload_any_section(user: AuthenticatedUser) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    return any(level_can_upload(level) for level in user.section_access.values())


def ai_access_mode(user: AuthenticatedUser) -> AiAccessMode:
    if user.role == UserRole.ADMIN:
        return "unlimited"
    has_unlimited = any(level_has_unlimited_ai(level) for level in user.section_access.values())
    if has_unlimited:
        return "unlimited"
    has_limited = any(level_can_use_ai(level) for level in user.section_access.values())
    if has_limited:
        return "limited"
    return "none"


def user_can_use_ai(user: AuthenticatedUser) -> bool:
    return ai_access_mode(user) != "none"


def ai_allowed_doc_types(user: AuthenticatedUser) -> list[str] | None:
    """None = все разделы (админ)."""
    if user.role == UserRole.ADMIN:
        return None
    return [
        doc_type
        for doc_type, level in user.section_access.items()
        if level_can_use_ai(level)
    ]


def require_ai_access(user: AuthenticatedUser) -> list[str] | None:
    allowed = ai_allowed_doc_types(user)
    if allowed is None:
        return None
    if not allowed:
        raise ApplicationError(
            "AI доступен при праве загрузки и скачивания в разделе "
            "или при «Полном доступе»",
            status_code=403,
            code="ai_access_denied",
        )
    return allowed


def can_manage_document_links(user: AuthenticatedUser, doc_type: str | None) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    level = access_for_doc_type(user.section_access, doc_type)
    return level_can_manage_document_links(level)


def require_section_manage_links(user: AuthenticatedUser, doc_type: str | None) -> None:
    require_section_view(user, doc_type)
    if not can_manage_document_links(user, doc_type):
        raise ApplicationError(
            "Связи документов доступны при полном доступе или праве загрузки в раздел",
            status_code=403,
            code="section_links_denied",
        )
