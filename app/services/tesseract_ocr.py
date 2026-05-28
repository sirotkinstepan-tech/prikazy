import io
import logging
import re
from dataclasses import dataclass
from decimal import Decimal

import fitz
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

MIN_MEANINGFUL_TEXT_CHARS = 20
MIN_UNIQUE_WORDS = 3
MIN_UNIQUE_WORD_RATIO = 0.25
PDF_BINARY_MARKERS = ("%PDF", "/Type", "endobj", "stream")


@dataclass(frozen=True)
class TesseractPageResult:
    page_number: int
    text: str
    confidence: float | None
    method: str


@dataclass(frozen=True)
class TesseractDocumentResult:
    full_text: str
    confidence: Decimal | None
    pages: list[TesseractPageResult]
    extraction_method: str


def is_meaningful_text(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) < MIN_MEANINGFUL_TEXT_CHARS:
        return False
    marker_hits = sum(1 for marker in PDF_BINARY_MARKERS if marker in cleaned)
    if marker_hits >= 2:
        return False
    words = re.findall(r"\w+", cleaned, flags=re.UNICODE)
    if not words:
        return False
    unique_words = {word.casefold() for word in words}
    if len(unique_words) < MIN_UNIQUE_WORDS:
        return False
    if len(unique_words) / len(words) < MIN_UNIQUE_WORD_RATIO:
        return False
    return True


def _average_confidence(confidences: list[float]) -> float | None:
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def _ocr_image(image: Image.Image, *, languages: str) -> tuple[str, float | None]:
    text = pytesseract.image_to_string(image, lang=languages)
    data = pytesseract.image_to_data(image, lang=languages, output_type=pytesseract.Output.DICT)
    confidences: list[float] = []
    for raw_conf in data.get("conf", []):
        try:
            value = float(raw_conf)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            confidences.append(value / 100.0)
    return text.strip(), _average_confidence(confidences)


def _extract_pdf_text(content: bytes) -> tuple[str, list[TesseractPageResult]]:
    document = fitz.open(stream=content, filetype="pdf")
    try:
        pages: list[TesseractPageResult] = []
        chunks: list[str] = []
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                chunks.append(text)
            pages.append(
                TesseractPageResult(
                    page_number=index,
                    text=text,
                    confidence=1.0 if text else None,
                    method="text_layer",
                )
            )
        return "\n\n".join(chunks).strip(), pages
    finally:
        document.close()


def _ocr_pdf_pages(content: bytes, *, languages: str, dpi_scale: float) -> list[TesseractPageResult]:
    document = fitz.open(stream=content, filetype="pdf")
    try:
        matrix = fitz.Matrix(dpi_scale, dpi_scale)
        pages: list[TesseractPageResult] = []
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            text, confidence = _ocr_image(image, languages=languages)
            pages.append(
                TesseractPageResult(
                    page_number=index,
                    text=text,
                    confidence=confidence,
                    method="ocr",
                )
            )
        return pages
    finally:
        document.close()


def process_pdf(content: bytes, *, languages: str, dpi_scale: float) -> TesseractDocumentResult:
    extracted_text, text_layer_pages = _extract_pdf_text(content)
    if is_meaningful_text(extracted_text):
        return TesseractDocumentResult(
            full_text=extracted_text,
            confidence=Decimal("1.0000"),
            pages=text_layer_pages,
            extraction_method="text_layer",
        )

    logger.info("pdf text layer empty or unusable, falling back to tesseract OCR")
    ocr_pages = _ocr_pdf_pages(content, languages=languages, dpi_scale=dpi_scale)
    full_text = "\n\n".join(page.text for page in ocr_pages if page.text).strip()
    if not full_text:
        raise RuntimeError("Tesseract OCR returned empty text for PDF")
    return TesseractDocumentResult(
        full_text=full_text,
        confidence=_decimal_confidence(_average_confidence([p.confidence for p in ocr_pages if p.confidence])),
        pages=ocr_pages,
        extraction_method="ocr",
    )


def process_image(content: bytes, *, languages: str) -> TesseractDocumentResult:
    image = Image.open(io.BytesIO(content))
    text, confidence = _ocr_image(image, languages=languages)
    if not text:
        raise RuntimeError("Tesseract OCR returned empty text for image")
    return TesseractDocumentResult(
        full_text=text,
        confidence=_decimal_confidence(confidence),
        pages=[
            TesseractPageResult(
                page_number=1,
                text=text,
                confidence=confidence,
                method="ocr",
            )
        ],
        extraction_method="ocr",
    )


def _decimal_confidence(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(value, 4)))
