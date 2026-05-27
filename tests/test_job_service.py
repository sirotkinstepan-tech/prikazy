from datetime import UTC, datetime
from uuid import uuid4

from app.repositories.jobs import ProcessingJobRepository


class FakeSession:
    def __init__(self):
        self.executed = False

    def execute(self, _statement):
        self.executed = True

        class Result:
            rowcount = 2

        return Result()


def test_cancel_queued_for_document_executes_update():
    session = FakeSession()
    repository = ProcessingJobRepository(session)

    cancelled = repository.cancel_queued_for_document(
        document_id=uuid4(),
        document_created_at=datetime.now(UTC),
    )

    assert cancelled == 2
    assert session.executed is True
