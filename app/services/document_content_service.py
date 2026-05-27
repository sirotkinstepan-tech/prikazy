from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ApplicationError
from app.repositories.documents import DocumentRepository
from app.services.storage_service import ObjectStorageService


@dataclass(frozen=True)
class DocumentFileContent:
    content: bytes
    mime_type: str
    filename: str
    size_bytes: int


class DocumentContentService:
    def __init__(self, session: Session):
        self.session = session

    def load_file(
        self,
        *,
        document_id: UUID,
        tenant_id: UUID,
        storage: ObjectStorageService,
    ) -> DocumentFileContent:
        repository = DocumentRepository(self.session)
        document = repository.get_for_tenant(document_id, tenant_id)
        if document is None:
            raise ApplicationError("Document not found", status_code=404, code="document_not_found")
        if document.storage_object is None:
            raise ApplicationError(
                "Document storage object is missing",
                status_code=404,
                code="storage_object_not_found",
            )

        content = storage.download_bytes(
            bucket=document.storage_object.bucket,
            object_key=document.storage_object.object_key,
        )
        filename = (
            document.source_filename
            or document.storage_object.original_filename
            or "document"
        )
        return DocumentFileContent(
            content=content,
            mime_type=document.mime_type,
            filename=filename,
            size_bytes=len(content),
        )
