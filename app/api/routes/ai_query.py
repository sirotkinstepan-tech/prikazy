from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import DbSessionDep, FullAccessUserDep, SettingsDep
from app.schemas.ai_query import AiQueryRequest, AiQueryResponse
from app.services.ai_query_service import AiQueryService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/query", response_model=AiQueryResponse)
def ask_database(
    body: AiQueryRequest,
    session: DbSessionDep,
    settings: SettingsDep,
    tenant_id: UUID,
    _user: FullAccessUserDep,
) -> AiQueryResponse:
    service = AiQueryService(session, settings)
    return service.ask(tenant_id=tenant_id, question=body.question)
