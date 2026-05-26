from dataclasses import dataclass
from decimal import Decimal

from app.services.document_extractor import extract_office_document_text
from app.services.mime_types import is_office_document


@dataclass(frozen=True)
class ExtractedFieldResult:
    field_name: str
    field_value: str
    field_type: str | None = None
    confidence: Decimal | None = None
    source_json: dict | None = None


@dataclass(frozen=True)
class OcrProviderResult:
    provider: str
    language: str | None
    full_text: str
    confidence: Decimal | None
    layout_json: dict | None
    page_data: dict | None
    extracted_fields: list[ExtractedFieldResult]


class OcrProvider:
    name = "base"

    def process(
        self,
        *,
        content: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> OcrProviderResult:
        raise NotImplementedError


class StubOcrProvider(OcrProvider):
    name = "stub"

    def process(
        self,
        *,
        content: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> OcrProviderResult:
        preview = content[:512].decode("utf-8", errors="ignore").strip()
        if not preview:
            preview = f"Stub OCR text for {filename or 'document'} with MIME type {mime_type}."
        return OcrProviderResult(
            provider=self.name,
            language="simple",
            full_text=preview,
            confidence=Decimal("0.9000"),
            layout_json={"provider": self.name, "blocks": []},
            page_data={"pages": [{"page_number": 1, "confidence": 0.9}]},
            extracted_fields=[],
        )


def get_ocr_provider(provider_name: str) -> OcrProvider:
    if provider_name == "stub":
        return StubOcrProvider()
    raise ValueError(f"Unsupported OCR provider: {provider_name}")


def process_document_content(
    *,
    content: bytes,
    mime_type: str,
    filename: str | None = None,
    ocr_provider_name: str = "stub",
) -> OcrProviderResult:
    if is_office_document(mime_type, filename):
        full_text = extract_office_document_text(
            content=content,
            mime_type=mime_type,
            filename=filename,
        )
        return OcrProviderResult(
            provider="office_extractor",
            language="simple",
            full_text=full_text,
            confidence=Decimal("1.0000"),
            layout_json={"provider": "office_extractor", "blocks": []},
            page_data={"pages": [{"page_number": 1, "confidence": 1.0}]},
            extracted_fields=[],
        )

    provider = get_ocr_provider(ocr_provider_name)
    return provider.process(content=content, mime_type=mime_type, filename=filename)
