from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKeyConstraint, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "document_created_at"],
            ["documents.id", "documents.created_at"],
        ),
        ForeignKeyConstraint(
            ["ocr_result_id", "ocr_result_processed_at"],
            ["ocr_results.id", "ocr_results.processed_at"],
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ocr_result_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    ocr_result_processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    source_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
