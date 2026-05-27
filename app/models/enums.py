from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    VALIDATED = "validated"
    FAILED = "failed"
    ARCHIVED = "archived"


class ProcessingJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProcessingJobType(StrEnum):
    OCR = "ocr"


class AccessLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    FULL_ACCESS = "full_access"

    @property
    def label(self) -> str:
        labels = {
            AccessLevel.READ: "Чтение",
            AccessLevel.WRITE: "Запись",
            AccessLevel.FULL_ACCESS: "Полный доступ",
        }
        return labels[self]
