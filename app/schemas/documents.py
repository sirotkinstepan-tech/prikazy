from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    created_at: datetime
    status: str
    job_id: UUID


class StorageObjectRead(BaseModel):
    id: UUID
    bucket: str
    object_key: str
    version_id: str | None = None
    sha256: str
    size_bytes: int
    mime_type: str
    original_filename: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobRead(BaseModel):
    id: UUID
    job_type: str
    status: str
    attempt: int
    max_attempts: int
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentRead(BaseModel):
    id: UUID
    created_at: datetime
    tenant_id: UUID
    status: str
    doc_type: str | None = None
    document_date: date | None = None
    counterparty_name: str | None = None
    title: str | None = None
    source_filename: str | None = None
    mime_type: str
    size_bytes: int
    sha256: str
    updated_at: datetime
    storage_object: StorageObjectRead | None = None
    latest_job: ProcessingJobRead | None = None
    preview_url: str | None = None
    download_url: str | None = None
    viewer_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    limit: int
    offset: int
    total: int


class ReprocessRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class OcrResultRead(BaseModel):
    id: UUID
    processed_at: datetime
    document_id: UUID
    job_id: UUID
    provider: str
    language: str | None = None
    full_text: str
    confidence: float | None = None
    layout_json: dict | None = None
    page_data: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class ExtractedFieldRead(BaseModel):
    id: UUID
    field_name: str
    field_value: str
    field_type: str | None = None
    confidence: float | None = None
    source_json: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentOcrResponse(BaseModel):
    ocr_result: OcrResultRead | None
    extracted_fields: list[ExtractedFieldRead] = []
