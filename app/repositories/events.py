from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.processing_event import ProcessingEvent


class ProcessingEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(
        self,
        *,
        document_id: UUID,
        document_created_at: datetime,
        event_type: str,
        message: str | None = None,
        job_id: UUID | None = None,
        payload: dict | None = None,
    ) -> ProcessingEvent:
        event = ProcessingEvent(
            document_id=document_id,
            document_created_at=document_created_at,
            job_id=job_id,
            event_type=event_type,
            message=message,
            payload=payload,
        )
        self.session.add(event)
        return event
