from dataclasses import dataclass
from decimal import Decimal

from app.services.document_extractor import extract_office_document_text
from app.services.mime_types import is_office_document
from app.services.tesseract_ocr import process_image, process_pdf


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


class TesseractOcrProvider(OcrProvider):
    name = "tesseract"

    def __init__(self, *, languages: str = "rus+eng", dpi_scale: float = 2.0):
        self.languages = languages
        self.dpi_scale = dpi_scale

    def process(
        self,
        *,
        content: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> OcrProviderResult:
        if mime_type == "application/pdf" or (filename and filename.lower().endswith(".pdf")):
            result = process_pdf(
                content,
                languages=self.languages,
                dpi_scale=self.dpi_scale,
            )
        elif mime_type.startswith("image/"):
            result = process_image(content, languages=self.languages)
        else:
            raise ValueError(f"Tesseract OCR does not support MIME type: {mime_type}")

        return OcrProviderResult(
            provider=self.name,
            language=self.languages,
            full_text=result.full_text,
            confidence=result.confidence,
            layout_json={
                "provider": self.name,
                "method": result.extraction_method,
                "pages": [
                    {
                        "page_number": page.page_number,
                        "method": page.method,
                        "confidence": page.confidence,
                    }
                    for page in result.pages
                ],
            },
            page_data={
                "pages": [
                    {
                        "page_number": page.page_number,
                        "confidence": page.confidence,
                        "method": page.method,
                    }
                    for page in result.pages
                ]
            },
            extracted_fields=[],
        )


def get_ocr_provider(
    provider_name: str,
    *,
    tesseract_languages: str = "rus+eng",
    tesseract_dpi_scale: float = 2.0,
) -> OcrProvider:
    if provider_name == "stub":
        return StubOcrProvider()
    if provider_name == "tesseract":
        return TesseractOcrProvider(
            languages=tesseract_languages,
            dpi_scale=tesseract_dpi_scale,
        )
    raise ValueError(f"Unsupported OCR provider: {provider_name}")


def process_document_content(
    *,
    content: bytes,
    mime_type: str,
    filename: str | None = None,
    ocr_provider_name: str = "tesseract",
    tesseract_languages: str = "rus+eng",
    tesseract_dpi_scale: float = 2.0,
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

    provider = get_ocr_provider(
        ocr_provider_name,
        tesseract_languages=tesseract_languages,
        tesseract_dpi_scale=tesseract_dpi_scale,
    )
    return provider.process(content=content, mime_type=mime_type, filename=filename)
