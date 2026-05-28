from app.core.document_sections import all_document_types
from app.models.enums import DocumentType, SectionAccessLevel, UserRole

SECTION_ACCESS_LABELS: dict[SectionAccessLevel, str] = {
    SectionAccessLevel.NONE: "Нет доступа",
    SectionAccessLevel.FULL: "Полный доступ (загрузка, скачивание, просмотр)",
    SectionAccessLevel.UPLOAD_VIEW_DOWNLOAD: "Загрузка, просмотр и скачивание",
    SectionAccessLevel.UPLOAD_VIEW: "Загрузка и просмотр",
    SectionAccessLevel.VIEW_DOWNLOAD: "Просмотр и скачивание (без загрузки)",
    SectionAccessLevel.VIEW_ONLY: "Только просмотр",
}


def section_access_label(level: SectionAccessLevel | str) -> str:
    if isinstance(level, str):
        try:
            level = SectionAccessLevel(level)
        except ValueError:
            return level
    return SECTION_ACCESS_LABELS.get(level, level.value)


def parse_section_access_level(value: str | None) -> SectionAccessLevel:
    if not value or value == SectionAccessLevel.NONE.value:
        return SectionAccessLevel.NONE
    try:
        return SectionAccessLevel(value)
    except ValueError as exc:
        from app.core.errors import ApplicationError

        raise ApplicationError(
            "Недопустимый уровень доступа к разделу",
            status_code=400,
            code="invalid_section_access",
        ) from exc


def level_can_view(level: SectionAccessLevel) -> bool:
    return level not in (SectionAccessLevel.NONE,)


def level_can_upload(level: SectionAccessLevel) -> bool:
    return level in (
        SectionAccessLevel.FULL,
        SectionAccessLevel.UPLOAD_VIEW_DOWNLOAD,
        SectionAccessLevel.UPLOAD_VIEW,
    )


def level_can_manage_document_links(level: SectionAccessLevel) -> bool:
    """Связи документов: полный доступ или право загрузки в раздел."""
    return level_can_upload(level)


def level_can_use_ai(level: SectionAccessLevel) -> bool:
    """AI доступен при праве загрузки и скачивания в разделе."""
    return level_can_upload(level) and level_can_download(level)


def level_has_unlimited_ai(level: SectionAccessLevel) -> bool:
    """Безлимитный AI только при «Полном доступе» к разделу."""
    return level == SectionAccessLevel.FULL


def level_can_download(level: SectionAccessLevel) -> bool:
    return level in (
        SectionAccessLevel.FULL,
        SectionAccessLevel.UPLOAD_VIEW_DOWNLOAD,
        SectionAccessLevel.VIEW_DOWNLOAD,
    )


def default_employee_section_access() -> dict[str, SectionAccessLevel]:
    """Значения по умолчанию в форме создания пользователя."""
    return {doc_type.value: SectionAccessLevel.NONE for doc_type in all_document_types()}


def empty_employee_section_access() -> dict[str, SectionAccessLevel]:
    return {doc_type.value: SectionAccessLevel.NONE for doc_type in all_document_types()}


def admin_section_access() -> dict[str, SectionAccessLevel]:
    return {doc_type.value: SectionAccessLevel.FULL for doc_type in all_document_types()}


def resolve_access_for_role(
    role: UserRole,
    stored: dict[str, SectionAccessLevel],
) -> dict[str, SectionAccessLevel]:
    if role == UserRole.ADMIN:
        return admin_section_access()
    result = empty_employee_section_access()
    for doc_type, level in stored.items():
        if doc_type in result:
            result[doc_type] = level
    return result


def allowed_doc_types_for_view(access: dict[str, SectionAccessLevel]) -> list[str]:
    return [doc_type for doc_type, level in access.items() if level_can_view(level)]


def access_for_doc_type(
    access: dict[str, SectionAccessLevel],
    doc_type: str | None,
) -> SectionAccessLevel:
    if not doc_type:
        return SectionAccessLevel.NONE
    return access.get(doc_type, SectionAccessLevel.NONE)


def section_access_options_for_ui() -> list[dict[str, str]]:
    order = [
        SectionAccessLevel.FULL,
        SectionAccessLevel.UPLOAD_VIEW_DOWNLOAD,
        SectionAccessLevel.UPLOAD_VIEW,
        SectionAccessLevel.VIEW_DOWNLOAD,
        SectionAccessLevel.VIEW_ONLY,
        SectionAccessLevel.NONE,
    ]
    return [
        {"value": level.value, "label": section_access_label(level)}
        for level in order
    ]


def document_sections_with_access_for_ui(
    access: dict[str, SectionAccessLevel],
) -> list[dict[str, str]]:
    from app.core.document_sections import section_label

    sections = []
    for doc_type in DocumentType:
        level = access.get(doc_type.value, SectionAccessLevel.NONE)
        if level_can_view(level):
            sections.append({"slug": doc_type.value, "label": section_label(doc_type)})
    return sections
