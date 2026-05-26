from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.document import Document
from app.models.processing_job import ProcessingJob


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, document: Document) -> Document:
        self.session.add(document)
        return document

    def get_for_tenant(self, document_id: UUID, tenant_id: UUID) -> Document | None:
        return self.session.scalars(
            select(Document)
            .options(joinedload(Document.storage_object))
            .where(Document.id == document_id, Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc())
            .limit(1)
        ).first()

    def find_duplicate(self, tenant_id: UUID, sha256: str) -> Document | None:
        return self.session.scalars(
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.sha256 == sha256)
            .order_by(Document.created_at.desc())
            .limit(1)
        ).first()

    def list_for_tenant(
        self,
        *,
        tenant_id: UUID,
        doc_type: str | None = None,
        status: str | None = None,
        document_date_from: date | None = None,
        document_date_to: date | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
        counterparty_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        filters = self._filters(
            tenant_id=tenant_id,
            doc_type=doc_type,
            status=status,
            document_date_from=document_date_from,
            document_date_to=document_date_to,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
            counterparty_name=counterparty_name,
        )
        base_query = select(Document).options(joinedload(Document.storage_object)).where(*filters)
        total = self.session.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
        items = list(
            self.session.scalars(
                base_query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
            )
        )
        return items, total

    def update_status(self, document: Document, status: str) -> None:
        document.status = status
        document.updated_at = datetime.now(UTC)

    def _filters(
        self,
        *,
        tenant_id: UUID,
        doc_type: str | None,
        status: str | None,
        document_date_from: date | None,
        document_date_to: date | None,
        created_at_from: datetime | None,
        created_at_to: datetime | None,
        counterparty_name: str | None,
    ) -> list:
        filters = [Document.tenant_id == tenant_id]
        if doc_type:
            filters.append(Document.doc_type == doc_type)
        if status:
            filters.append(Document.status == status)
        if document_date_from:
            filters.append(Document.document_date >= document_date_from)
        if document_date_to:
            filters.append(Document.document_date <= document_date_to)
        if created_at_from:
            filters.append(Document.created_at >= created_at_from)
        if created_at_to:
            filters.append(Document.created_at <= created_at_to)
        if counterparty_name:
            filters.append(Document.counterparty_name.ilike(f"%{counterparty_name}%"))
        return filters

    def latest_job_for_document(self, document: Document) -> ProcessingJob | None:
        return self.session.scalars(
            select(ProcessingJob)
            .where(
                ProcessingJob.document_id == document.id,
                ProcessingJob.document_created_at == document.created_at,
            )
            .order_by(ProcessingJob.created_at.desc())
            .limit(1)
        ).first()
