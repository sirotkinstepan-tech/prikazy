from typing import Literal
from uuid import UUID

from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.http_utils import build_content_disposition
from app.core.config import Settings
from app.services.document_content_service import DocumentContentService
from app.services.storage_service import ObjectStorageService


def build_document_file_response(
    session: Session,
    settings: Settings,
    *,
    document_id: UUID,
    tenant_id: UUID,
    disposition: Literal["inline", "attachment"],
) -> Response:
    file_content = DocumentContentService(session).load_file(
        document_id=document_id,
        tenant_id=tenant_id,
        storage=ObjectStorageService(settings),
    )
    return Response(
        content=file_content.content,
        media_type=file_content.mime_type,
        headers={
            "Content-Disposition": build_content_disposition(disposition, file_content.filename),
            "Content-Length": str(file_content.size_bytes),
            "Cache-Control": "private, max-age=3600",
        },
    )
