from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentRelation(Base):
    __tablename__ = "document_relations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    from_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    from_document_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    to_document_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    link_label: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
