from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.enums import SectionAccessLevel
from app.models.user_section_access import UserSectionAccess


class UserSectionAccessRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_user(self, user_id: UUID) -> dict[str, SectionAccessLevel]:
        rows = self.session.scalars(
            select(UserSectionAccess).where(UserSectionAccess.user_id == user_id)
        ).all()
        result: dict[str, SectionAccessLevel] = {}
        for row in rows:
            try:
                result[row.doc_type] = SectionAccessLevel(row.access_level)
            except ValueError:
                continue
        return result

    def replace_for_user(
        self,
        user_id: UUID,
        access: dict[str, SectionAccessLevel],
    ) -> None:
        self.session.execute(delete(UserSectionAccess).where(UserSectionAccess.user_id == user_id))
        for doc_type, level in access.items():
            self.session.add(
                UserSectionAccess(
                    user_id=user_id,
                    doc_type=doc_type,
                    access_level=level.value,
                )
            )
