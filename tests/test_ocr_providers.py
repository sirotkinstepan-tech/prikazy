import pytest

from app.services.ocr_provider import StubOcrProvider, get_ocr_provider, process_document_content


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
