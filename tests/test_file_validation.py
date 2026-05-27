import pytest

from app.core.errors import ApplicationError
from app.services.file_validation import validate_file_signature


def test_validate_pdf_signature():
    validate_file_signature(mime_type="application/pdf", content=b"%PDF-1.4 test")


def test_validate_pdf_rejects_wrong_content():
    with pytest.raises(ApplicationError) as exc:
        validate_file_signature(mime_type="application/pdf", content=b"not-a-pdf")
    assert exc.value.code == "invalid_file_signature"


def test_validate_png_signature():
    validate_file_signature(
        mime_type="image/png",
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 8,
    )
