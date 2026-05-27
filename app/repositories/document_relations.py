from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_relation import DocumentRelation


@dataclass(frozen=True)
class RelatedDocumentView:
    relation_id: UUID
    document_id: UUID
    document_created_at: datetime
    title: str | None
    source_filename: str | None
    doc_type: str | None
    status: str
    link_label: str | None
    direction: str


class DocumentRelationRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, relation: DocumentRelation) -> DocumentRelation:
        self.session.add(relation)
        return relation

    def get(self, relation_id: UUID, tenant_id: UUID) -> DocumentRelation | None:
        return self.session.scalars(
            select(DocumentRelation).where(
                DocumentRelation.id == relation_id,
                DocumentRelation.tenant_id == tenant_id,
            )
        ).first()

    def delete(self, relation: DocumentRelation) -> None:
        self.session.delete(relation)

    def exists_pair(
        self,
        *,
        tenant_id: UUID,
        from_document_id: UUID,
        from_document_created_at: datetime,
        to_document_id: UUID,
        to_document_created_at: datetime,
    ) -> bool:
        return (
            self.session.scalars(
                select(DocumentRelation.id).where(
                    DocumentRelation.tenant_id == tenant_id,
                    DocumentRelation.from_document_id == from_document_id,
                    DocumentRelation.from_document_created_at == from_document_created_at,
                    DocumentRelation.to_document_id == to_document_id,
                    DocumentRelation.to_document_created_at == to_document_created_at,
                )
            ).first()
            is not None
        )

    def list_for_document(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        document_created_at: datetime,
    ) -> list[RelatedDocumentView]:
        sql = text(
            """
            SELECT
                r.id AS relation_id,
                CASE
                    WHEN r.from_document_id = :document_id
                         AND r.from_document_created_at = :document_created_at
                    THEN r.to_document_id
                    ELSE r.from_document_id
                END AS document_id,
                CASE
                    WHEN r.from_document_id = :document_id
                         AND r.from_document_created_at = :document_created_at
                    THEN r.to_document_created_at
                    ELSE r.from_document_created_at
                END AS document_created_at,
                d.title,
                d.source_filename,
                d.doc_type,
                d.status,
                r.link_label,
                CASE
                    WHEN r.from_document_id = :document_id
                         AND r.from_document_created_at = :document_created_at
                    THEN 'outgoing'
                    ELSE 'incoming'
                END AS direction
            FROM document_relations r
            JOIN documents d
              ON d.id = CASE
                    WHEN r.from_document_id = :document_id
                         AND r.from_document_created_at = :document_created_at
                    THEN r.to_document_id
                    ELSE r.from_document_id
                 END
             AND d.created_at = CASE
                    WHEN r.from_document_id = :document_id
                         AND r.from_document_created_at = :document_created_at
                    THEN r.to_document_created_at
                    ELSE r.from_document_created_at
                 END
            WHERE r.tenant_id = :tenant_id
              AND (
                    (r.from_document_id = :document_id
                     AND r.from_document_created_at = :document_created_at)
                 OR (r.to_document_id = :document_id
                     AND r.to_document_created_at = :document_created_at)
              )
            ORDER BY r.created_at DESC
            """
        )
        rows = self.session.execute(
            sql,
            {
                "tenant_id": tenant_id,
                "document_id": document_id,
                "document_created_at": document_created_at,
            },
        ).mappings().all()
        return [
            RelatedDocumentView(
                relation_id=row["relation_id"],
                document_id=row["document_id"],
                document_created_at=row["document_created_at"],
                title=row["title"],
                source_filename=row["source_filename"],
                doc_type=row["doc_type"],
                status=row["status"],
                link_label=row["link_label"],
                direction=row["direction"],
            )
            for row in rows
        ]

    def list_for_documents_batch(
        self,
        *,
        tenant_id: UUID,
        document_keys: list[tuple[UUID, datetime]],
    ) -> dict[tuple[UUID, datetime], list[RelatedDocumentView]]:
        if not document_keys:
            return {}

        by_doc: dict[tuple[UUID, datetime], list[RelatedDocumentView]] = {
            key: [] for key in document_keys
        }
        for document_id, document_created_at in document_keys:
            related = self.list_for_document(
                tenant_id=tenant_id,
                document_id=document_id,
                document_created_at=document_created_at,
            )
            by_doc[(document_id, document_created_at)] = related
        return by_doc

    def list_related_by_document_ids(
        self,
        *,
        tenant_id: UUID,
        document_ids: list[UUID],
    ) -> dict[UUID, list[RelatedDocumentView]]:
        result: dict[UUID, list[RelatedDocumentView]] = {doc_id: [] for doc_id in document_ids}
        for document_id in document_ids:
            document = self.session.scalars(
                select(Document)
                .where(Document.id == document_id, Document.tenant_id == tenant_id)
                .order_by(Document.created_at.desc())
                .limit(1)
            ).first()
            if document is None:
                continue
            result[document_id] = self.list_for_document(
                tenant_id=tenant_id,
                document_id=document.id,
                document_created_at=document.created_at,
            )
        return result
