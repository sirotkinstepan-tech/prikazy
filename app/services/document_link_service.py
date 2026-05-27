from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ApplicationError
from app.models.document_relation import DocumentRelation
from app.repositories.document_relations import DocumentRelationRepository, RelatedDocumentView
from app.repositories.documents import DocumentRepository


@dataclass(frozen=True)
class CreateDocumentLinkCommand:
    tenant_id: UUID
    from_document_id: UUID
    to_document_id: UUID
    link_label: str | None = None
    created_by_user_id: UUID | None = None


class DocumentLinkService:
    def __init__(self, session: Session):
        self.session = session
        self.relations = DocumentRelationRepository(session)
        self.documents = DocumentRepository(session)

    def list_related(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        document_created_at,
    ) -> list[RelatedDocumentView]:
        return self.relations.list_for_document(
            tenant_id=tenant_id,
            document_id=document_id,
            document_created_at=document_created_at,
        )

    def create_link(self, command: CreateDocumentLinkCommand) -> DocumentRelation:
        if command.from_document_id == command.to_document_id:
            raise ApplicationError(
                "Нельзя связать документ с самим собой",
                status_code=400,
                code="self_link_forbidden",
            )

        from_doc = self.documents.get_for_tenant(command.from_document_id, command.tenant_id)
        to_doc = self.documents.get_for_tenant(command.to_document_id, command.tenant_id)
        if from_doc is None or to_doc is None:
            raise ApplicationError(
                "Один из документов не найден",
                status_code=404,
                code="document_not_found",
            )

        label = command.link_label.strip() if command.link_label else None
        if self.relations.exists_pair(
            tenant_id=command.tenant_id,
            from_document_id=from_doc.id,
            from_document_created_at=from_doc.created_at,
            to_document_id=to_doc.id,
            to_document_created_at=to_doc.created_at,
        ):
            raise ApplicationError(
                "Такая связь уже существует",
                status_code=409,
                code="link_already_exists",
            )

        relation = DocumentRelation(
            tenant_id=command.tenant_id,
            from_document_id=from_doc.id,
            from_document_created_at=from_doc.created_at,
            to_document_id=to_doc.id,
            to_document_created_at=to_doc.created_at,
            link_label=label,
            created_by_user_id=command.created_by_user_id,
        )
        self.relations.add(relation)
        self.session.commit()
        return relation

    def remove_link(self, *, relation_id: UUID, tenant_id: UUID) -> None:
        relation = self.relations.get(relation_id, tenant_id)
        if relation is None:
            raise ApplicationError(
                "Связь не найдена",
                status_code=404,
                code="link_not_found",
            )
        self.relations.delete(relation)
        self.session.commit()
