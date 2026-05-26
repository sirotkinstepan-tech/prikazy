from pathlib import PurePath

WORD_MIME_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }
)

EXCEL_MIME_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }
)

OFFICE_MIME_TYPES = WORD_MIME_TYPES | EXCEL_MIME_TYPES

EXTENSION_MIME_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


def resolve_mime_type(mime_type: str, filename: str | None = None) -> str:
    normalized = (mime_type or "").strip().lower()
    if normalized and normalized != "application/octet-stream":
        return normalized
    if filename:
        extension = PurePath(filename).suffix.lower()
        return EXTENSION_MIME_TYPES.get(extension, normalized or "application/octet-stream")
    return normalized or "application/octet-stream"


def is_word_document(mime_type: str, filename: str | None = None) -> bool:
    resolved = resolve_mime_type(mime_type, filename)
    if resolved in WORD_MIME_TYPES:
        return True
    if filename:
        return PurePath(filename).suffix.lower() in {".docx", ".doc"}
    return False


def is_excel_document(mime_type: str, filename: str | None = None) -> bool:
    resolved = resolve_mime_type(mime_type, filename)
    if resolved in EXCEL_MIME_TYPES:
        return True
    if filename:
        return PurePath(filename).suffix.lower() in {".xlsx", ".xls"}
    return False


def is_office_document(mime_type: str, filename: str | None = None) -> bool:
    return is_word_document(mime_type, filename) or is_excel_document(mime_type, filename)
