from app.core.errors import ApplicationError
from app.models.enums import DocumentType

DOCUMENT_SECTION_LABELS: dict[DocumentType, str] = {
    DocumentType.PRIKAZ: "Приказы",
    DocumentType.INTERNAL_CONTRACT: "Договоры внутренние",
    DocumentType.EXTERNAL_CONTRACT: "Договоры внешние",
    DocumentType.LNA: "ЛНА",
    DocumentType.TECHNOLOG: "Технолог",
    DocumentType.KADRY: "Кадры",
    DocumentType.INCOMING_CORRESPONDENCE: "Входящая корреспонденция",
    DocumentType.OUTGOING_CORRESPONDENCE: "Исходящая корреспонденция",
}


def all_document_types() -> list[DocumentType]:
    return list(DocumentType)


def section_label(doc_type: DocumentType) -> str:
    return DOCUMENT_SECTION_LABELS[doc_type]


def section_label_for(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return section_label(DocumentType(value))
    except ValueError:
        return value


def resolve_doc_type_slug(value: str | None) -> str | None:
    """Map section slug or Russian label to canonical doc_type value."""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return DocumentType(cleaned).value
    except ValueError:
        pass
    lowered = cleaned.lower()
    for doc_type in DocumentType:
        if doc_type.value.lower() == lowered:
            return doc_type.value
        if DOCUMENT_SECTION_LABELS[doc_type].lower() == lowered:
            return doc_type.value
    return cleaned


def validate_doc_type(value: str) -> str:
    try:
        return DocumentType(value).value
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DocumentType)
        raise ApplicationError(
            f"Unknown doc_type '{value}'. Allowed values: {allowed}",
            status_code=400,
            code="invalid_doc_type",
        ) from exc


def normalize_doc_type_list(values: list[str] | None) -> list[str] | None:
    if not values:
        return None

    normalized: list[str] = []
    for raw in values:
        for part in raw.split(","):
            part = part.strip()
            if part:
                normalized.append(validate_doc_type(part))
    return normalized or None


def resolve_doc_type_filters(
    *,
    doc_type: str | None,
    doc_types: list[str] | None,
) -> list[str] | None:
    normalized = normalize_doc_type_list(doc_types)
    if normalized is not None:
        return normalized
    if doc_type is not None:
        return [validate_doc_type(doc_type)]
    return None


def document_sections_for_ui() -> list[dict[str, str]]:
    return [
        {"slug": doc_type.value, "label": section_label(doc_type)}
        for doc_type in all_document_types()
    ]
