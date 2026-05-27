from app.auth.service import AuthenticatedUser
from app.core.document_sections import document_sections_for_ui
from app.core.section_permissions import document_sections_with_access_for_ui
from app.web.section_access import user_allowed_doc_types, user_can_upload_any_section


def portal_template_context(user: AuthenticatedUser) -> dict:
    allowed = user_allowed_doc_types(user)
    if allowed is None:
        sections = document_sections_for_ui()
        show_all = True
    else:
        sections = document_sections_with_access_for_ui(user.section_access)
        show_all = len(allowed) > 1
    return {
        "portal_sections": sections,
        "can_upload_any": user_can_upload_any_section(user),
        "show_all_section_tab": show_all,
    }


def merge_doc_types_filter(
    user: AuthenticatedUser,
    section: str | None,
    doc_types: list[str] | None,
) -> list[str] | None:
    allowed = user_allowed_doc_types(user)
    if allowed is None:
        return doc_types
    if not allowed:
        return ["__no_access__"]
    if doc_types is None:
        return allowed
    intersected = [value for value in doc_types if value in allowed]
    return intersected or ["__no_access__"]
