from sqlalchemy.orm import Session

from app.models.storage_object import StorageObject


class StorageObjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, storage_object: StorageObject) -> StorageObject:
        self.session.add(storage_object)
        return storage_object
