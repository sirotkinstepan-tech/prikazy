from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.storage_object import StorageObject


class StorageObjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, storage_object: StorageObject) -> StorageObject:
        self.session.add(storage_object)
        return storage_object

    def get(self, storage_object_id: UUID) -> StorageObject | None:
        return self.session.get(StorageObject, storage_object_id)

    def delete(self, storage_object: StorageObject) -> None:
        self.session.delete(storage_object)

    def list_by_ids(self, storage_object_ids: list[UUID]) -> list[StorageObject]:
        if not storage_object_ids:
            return []
        return list(
            self.session.scalars(
                select(StorageObject).where(StorageObject.id.in_(storage_object_ids))
            )
        )
