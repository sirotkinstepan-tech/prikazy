from datetime import UTC, datetime
from uuid import uuid4

from app.models.ocr_result import OcrResult
from app.repositories.ocr_results import OcrResultRepository
from app.services.ocr_provider import StubOcrProvider


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def test_stub_provider_returns_persistable_ocr_result():
    document_id = uuid4()
    document_created_at = datetime.now(UTC)
    job_id = uuid4()
    provider_result = StubOcrProvider().process(
        content=b"Invoice ACME total 100",
        mime_type="application/pdf",
        filename="invoice.pdf",
    )
    ocr_result = OcrResult(
        id=uuid4(),
        processed_at=datetime.now(UTC),
        document_id=document_id,
        document_created_at=document_created_at,
        job_id=job_id,
        provider=provider_result.provider,
        language=provider_result.language,
        full_text=provider_result.full_text,
        confidence=provider_result.confidence,
        layout_json=provider_result.layout_json,
        page_data=provider_result.page_data,
        created_at=datetime.now(UTC),
    )
    session = FakeSession()
    repository = OcrResultRepository(session)

    repository.add(ocr_result)

    assert session.added == [ocr_result]
    assert ocr_result.full_text == "Invoice ACME total 100"
    assert ocr_result.provider == "stub"
    assert ocr_result.confidence is not None
