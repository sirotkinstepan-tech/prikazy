from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSectionAccess(Base):
    __tablename__ = "user_section_access"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    doc_type: Mapped[str] = mapped_column(Text, primary_key=True)
    access_level: Mapped[str] = mapped_column(Text, nullable=False)
