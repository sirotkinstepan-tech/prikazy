from pydantic import BaseModel


class DocumentSectionRead(BaseModel):
    slug: str
    label: str


class DocumentSectionsResponse(BaseModel):
    items: list[DocumentSectionRead]
