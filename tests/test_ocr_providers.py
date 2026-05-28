from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.ocr_provider import (
    StubOcrProvider,
    TesseractOcrProvider,
    get_ocr_provider,
    process_document_content,
)
from app.services.tesseract_ocr import (
    TesseractDocumentResult,
    TesseractPageResult,
    is_meaningful_text,
    process_pdf,
)


def test_stub_provider_returns_decoded_preview_for_pdf_bytes():
    result = StubOcrProvider().process(
        content=b"%PDF-1.4\n% empty scan\n",
        mime_type="application/pdf",
        filename="order.pdf",
    )

    assert "%PDF-1.4" in result.full_text
    assert result.provider == "stub"


def test_stub_provider_uses_fallback_when_content_is_empty():
    result = StubOcrProvider().process(
        content=b"",
        mime_type="application/pdf",
        filename="scan.pdf",
    )

    assert "Stub OCR text" in result.full_text
    assert "scan.pdf" in result.full_text


def test_process_document_content_routes_plain_text_to_stub_provider():
    result = process_document_content(
        content=b"plain text order",
        mime_type="application/pdf",
        filename="order.pdf",
        ocr_provider_name="stub",
    )

    assert result.provider == "stub"
    assert "plain text order" in result.full_text


def test_get_ocr_provider_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unsupported OCR provider"):
        get_ocr_provider("unknown")


def test_get_ocr_provider_returns_tesseract():
    provider = get_ocr_provider("tesseract", tesseract_languages="rus+eng")
    assert provider.name == "tesseract"


def test_is_meaningful_text_rejects_pdf_binary_preview():
    assert is_meaningful_text("%PDF-1.4\n/Type /Catalog\nendobj\nstream") is False


def test_is_meaningful_text_accepts_russian_contract_title():
    assert is_meaningful_text("Покупка тележки для продажи мороженого") is True


def test_is_meaningful_text_rejects_scanner_watermark_spam():
    watermark_text = "\n\n".join(["AnyScanner"] * 9)
    assert is_meaningful_text(watermark_text) is False


@patch("app.services.ocr_provider.process_pdf")
def test_tesseract_provider_processes_pdf(mock_process_pdf):
    mock_process_pdf.return_value = TesseractDocumentResult(
        full_text="Покупка тележки для продажи мороженого",
        confidence=Decimal("0.9100"),
        pages=[
            TesseractPageResult(
                page_number=1,
                text="Покупка тележки для продажи мороженого",
                confidence=0.91,
                method="ocr",
            )
        ],
        extraction_method="ocr",
    )

    result = TesseractOcrProvider(languages="rus+eng").process(
        content=b"%PDF-1.4",
        mime_type="application/pdf",
        filename="contract.pdf",
    )

    assert result.provider == "tesseract"
    assert "тележки" in result.full_text
    assert result.confidence == Decimal("0.9100")
    mock_process_pdf.assert_called_once()


@patch("app.services.tesseract_ocr._extract_pdf_text")
def test_process_pdf_uses_text_layer_when_meaningful(mock_extract_pdf_text):
    mock_extract_pdf_text.return_value = (
        "Покупка тележки для продажи мороженого",
        [
            TesseractPageResult(
                page_number=1,
                text="Покупка тележки для продажи мороженого",
                confidence=1.0,
                method="text_layer",
            )
        ],
    )

    result = process_pdf(b"%PDF-1.4", languages="rus+eng", dpi_scale=2.0)

    assert result.extraction_method == "text_layer"
    assert result.full_text.startswith("Покупка")


@patch("app.services.tesseract_ocr._ocr_pdf_pages")
@patch("app.services.tesseract_ocr._extract_pdf_text")
def test_process_pdf_falls_back_to_ocr_for_scanner_watermarks(
    mock_extract_pdf_text,
    mock_ocr_pdf_pages,
):
    watermark_text = "\n\n".join(["AnyScanner"] * 9)
    mock_extract_pdf_text.return_value = (
        watermark_text,
        [
            TesseractPageResult(
                page_number=index,
                text="AnyScanner",
                confidence=1.0,
                method="text_layer",
            )
            for index in range(1, 10)
        ],
    )
    mock_ocr_pdf_pages.return_value = [
        TesseractPageResult(
            page_number=1,
            text="ДОГОВОР ИЗГОТОВЛЕНИЯ И ПОСТАВКИ ТОВАРА",
            confidence=0.94,
            method="ocr",
        )
    ]

    result = process_pdf(b"%PDF-1.4", languages="rus+eng", dpi_scale=2.0)

    assert result.extraction_method == "ocr"
    assert "ДОГОВОР" in result.full_text
    mock_ocr_pdf_pages.assert_called_once()


@patch("app.services.tesseract_ocr._ocr_pdf_pages")
@patch("app.services.tesseract_ocr._extract_pdf_text")
def test_process_pdf_falls_back_to_ocr(mock_extract_pdf_text, mock_ocr_pdf_pages):
    mock_extract_pdf_text.return_value = (
        "%PDF-1.4 /Type /Catalog",
        [TesseractPageResult(page_number=1, text="%PDF-1.4", confidence=None, method="text_layer")],
    )
    mock_ocr_pdf_pages.return_value = [
        TesseractPageResult(
            page_number=1,
            text="Договор аренды помещения",
            confidence=0.88,
            method="ocr",
        )
    ]

    result = process_pdf(b"%PDF-1.4", languages="rus+eng", dpi_scale=2.0)

    assert result.extraction_method == "ocr"
    assert "Договор аренды" in result.full_text
    mock_ocr_pdf_pages.assert_called_once()
