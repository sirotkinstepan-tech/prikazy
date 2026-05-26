from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import DbSessionDep
from app.core.errors import ApplicationError
from app.repositories.search import SearchRepository
from app.schemas.search import SearchResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search_documents(
    session: DbSessionDep,
    tenant_id: UUID,
    q: str = Query(min_length=1),
    doc_type: str | None = None,
    status: str | None = None,
    document_date_from: date | None = None,
    document_date_to: date | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    counterparty_name: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    if not q.strip():
        raise ApplicationError(
            "Search query must not be empty",
            status_code=400,
            code="empty_query",
        )

    repository = SearchRepository(session)
    items, total = repository.search(
        tenant_id=tenant_id,
        query=q,
        doc_type=doc_type,
        status=status,
        document_date_from=document_date_from,
        document_date_to=document_date_to,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        counterparty_name=counterparty_name,
        limit=limit,
        offset=offset,
    )
    return SearchResponse(items=items, limit=limit, offset=offset, total=total)
