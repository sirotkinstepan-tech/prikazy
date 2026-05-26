from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extracted_field import ExtractedField
from app.models.ocr_result import OcrResult


class OcrResultRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, ocr_result: OcrResult) -> OcrResult:
        self.session.add(ocr_result)
        return ocr_result

    def add_extracted_field(self, extracted_field: ExtractedField) -> ExtractedField:
        self.session.add(extracted_field)
        return extracted_field

    def latest_for_document(
        self,
        document_id: UUID,
        document_created_at: datetime,
    ) -> OcrResult | None:
        return self.session.scalars(
            select(OcrResult)
            .where(
                OcrResult.document_id == document_id,
                OcrResult.document_created_at == document_created_at,
            )
            .order_by(OcrResult.processed_at.desc())
            .limit(1)
        ).first()

    def fields_for_result(self, ocr_result: OcrResult) -> list[ExtractedField]:
        return list(
            self.session.scalars(
                select(ExtractedField)
                .where(
                    ExtractedField.ocr_result_id == ocr_result.id,
                    ExtractedField.ocr_result_processed_at == ocr_result.processed_at,
                )
                .order_by(ExtractedField.created_at)
            )
        )
