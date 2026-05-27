from datetime import date
from uuid import UUID

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    document_id: UUID
    title: str | None = None
    source_filename: str | None = None
    status: str
    doc_type: str | None = None
    document_date: date | None = None
    counterparty_name: str | None = None
    rank: float
    snippet: str | None = None


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    limit: int
    offset: int
    total: int
