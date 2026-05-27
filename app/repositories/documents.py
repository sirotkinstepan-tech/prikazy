from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.repositories.search import SearchRepository


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
        doc_types: list[str] | None = None,
        status: str | None = None,
        document_date_from: date | None = None,
        document_date_to: date | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
        counterparty_name: str | None = None,
        text_query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        if text_query and text_query.strip():
            return self._list_for_tenant_by_text_search(
                tenant_id=tenant_id,
                text_query=text_query.strip(),
                doc_type=doc_type,
                doc_types=doc_types,
                status=status,
                document_date_from=document_date_from,
                document_date_to=document_date_to,
                created_at_from=created_at_from,
                created_at_to=created_at_to,
                counterparty_name=counterparty_name,
                limit=limit,
                offset=offset,
            )

        filters = self._filters(
            tenant_id=tenant_id,
            doc_type=doc_type,
            doc_types=doc_types,
            status=status,
            document_date_from=document_date_from,
            document_date_to=document_date_to,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
            counterparty_name=counterparty_name,
            text_query=text_query,
        )
        base_query = select(Document).options(joinedload(Document.storage_object)).where(*filters)
        total = self.session.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
        items = list(
            self.session.scalars(
                base_query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
            )
        )
        return items, total

    def _list_for_tenant_by_text_search(
        self,
        *,
        tenant_id: UUID,
        text_query: str,
        doc_type: str | None,
        doc_types: list[str] | None,
        status: str | None,
        document_date_from: date | None,
        document_date_to: date | None,
        created_at_from: datetime | None,
        created_at_to: datetime | None,
        counterparty_name: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], int]:
        rows, total = SearchRepository(self.session).search(
            tenant_id=tenant_id,
            query=text_query,
            doc_type=doc_type,
            doc_types=doc_types,
            status=status,
            document_date_from=document_date_from,
            document_date_to=document_date_to,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
            counterparty_name=counterparty_name,
            limit=limit,
            offset=offset,
        )
        if not rows:
            return [], total

        document_ids = [row["document_id"] for row in rows]
        documents = list(
            self.session.scalars(
                select(Document)
                .options(joinedload(Document.storage_object))
                .where(Document.tenant_id == tenant_id, Document.id.in_(document_ids))
            )
        )
        documents_by_id = {document.id: document for document in documents}
        items = [
            documents_by_id[document_id]
            for document_id in document_ids
            if document_id in documents_by_id
        ]
        return items, total

    def update_status(self, document: Document, status: str) -> None:
        document.status = status
        document.updated_at = datetime.now(UTC)

    def _filters(
        self,
        *,
        tenant_id: UUID,
        doc_type: str | None,
        doc_types: list[str] | None,
        status: str | None,
        document_date_from: date | None,
        document_date_to: date | None,
        created_at_from: datetime | None,
        created_at_to: datetime | None,
        counterparty_name: str | None,
        text_query: str | None,
    ) -> list:
        filters = [Document.tenant_id == tenant_id]
        if doc_types:
            filters.append(Document.doc_type.in_(doc_types))
        elif doc_type:
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
        if text_query:
            pattern = f"%{text_query.strip()}%"
            filters.append(
                or_(
                    Document.title.ilike(pattern),
                    Document.source_filename.ilike(pattern),
                )
            )
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
