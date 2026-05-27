from app.core.errors import ApplicationError

PDF_SIGNATURE = b"%PDF"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
ZIP_SIGNATURE = b"PK\x03\x04"
TIFF_LE_SIGNATURE = b"II*\x00"
TIFF_BE_SIGNATURE = b"MM\x00*"


def validate_file_signature(*, mime_type: str, content: bytes) -> None:
    if not content:
        raise ApplicationError("Uploaded file is empty", status_code=400, code="empty_file")

    if mime_type == "application/pdf":
        if not content.startswith(PDF_SIGNATURE):
            raise _signature_error("PDF")
        return

    if mime_type == "image/png":
        if not content.startswith(PNG_SIGNATURE):
            raise _signature_error("PNG")
        return

    if mime_type == "image/jpeg":
        if not content.startswith(JPEG_SIGNATURE):
            raise _signature_error("JPEG")
        return

    if mime_type == "image/tiff":
        if not content.startswith(TIFF_LE_SIGNATURE) and not content.startswith(TIFF_BE_SIGNATURE):
            raise _signature_error("TIFF")
        return

    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.ms-excel",
    ):
        if not content.startswith(ZIP_SIGNATURE):
            raise _signature_error("Office")
        return

    raise ApplicationError(
        f"Unsupported MIME type: {mime_type}",
        status_code=415,
        code="unsupported_mime_type",
    )


def _signature_error(kind: str) -> ApplicationError:
    return ApplicationError(
        f"File content does not match declared type ({kind})",
        status_code=415,
        code="invalid_file_signature",
    )
