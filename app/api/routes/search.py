from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.access import ensure_tenant_id, require_api_section_view, resolve_api_doc_types
from app.api.dependencies import CurrentUserDep, DbSessionDep
from app.core.errors import ApplicationError
from app.repositories.search import SearchRepository
from app.schemas.search import SearchResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search_documents(
    user: CurrentUserDep,
    session: DbSessionDep,
    tenant_id: UUID | None = None,
    q: str = Query(min_length=1),
    doc_type: str | None = None,
    doc_types: list[str] | None = Query(default=None),
    status: str | None = None,
    document_date_from: date | None = None,
    document_date_to: date | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    counterparty_name: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    ensure_tenant_id(user, tenant_id)
    if not q.strip():
        raise ApplicationError(
            "Search query must not be empty",
            status_code=400,
            code="empty_query",
        )

    if doc_type:
        require_api_section_view(user, doc_type)

    resolved_doc_types = resolve_api_doc_types(user, doc_type=doc_type, doc_types=doc_types)
    repository = SearchRepository(session)
    items, total = repository.search(
        tenant_id=user.tenant_id,
        query=q,
        doc_types=resolved_doc_types,
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
