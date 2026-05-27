from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    VALIDATED = "validated"
    FAILED = "failed"
    ARCHIVED = "archived"


class UserRole(StrEnum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class ProcessingJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProcessingJobType(StrEnum):
    OCR = "ocr"


class DocumentType(StrEnum):
    PRIKAZ = "prikaz"
    INTERNAL_CONTRACT = "internal_contract"
    EXTERNAL_CONTRACT = "external_contract"
    LNA = "lna"


class SectionAccessLevel(StrEnum):
    """Права сотрудника на раздел (тип документа)."""

    NONE = "none"
    FULL = "full"
    UPLOAD_VIEW_DOWNLOAD = "upload_view_download"
    UPLOAD_VIEW = "upload_view"
    VIEW_DOWNLOAD = "view_download"
    VIEW_ONLY = "view_only"
