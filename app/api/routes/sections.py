from fastapi import APIRouter

from app.core.document_sections import all_document_types, section_label
from app.schemas.sections import DocumentSectionRead, DocumentSectionsResponse

router = APIRouter(tags=["sections"])


@router.get("/sections", response_model=DocumentSectionsResponse)
def list_document_sections() -> DocumentSectionsResponse:
    items = [
        DocumentSectionRead(slug=doc_type.value, label=section_label(doc_type))
        for doc_type in all_document_types()
    ]
    return DocumentSectionsResponse(items=items)
