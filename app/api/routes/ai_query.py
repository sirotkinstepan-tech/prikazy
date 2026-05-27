from fastapi import APIRouter

from app.api.dependencies import AiUserDep, DbSessionDep, SettingsDep
from app.schemas.ai_query import AiQueryRequest, AiQueryResponse
from app.services.ai_query_service import AiQueryService
from app.web.section_access import ai_allowed_doc_types

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/query", response_model=AiQueryResponse)
def ask_database(
    body: AiQueryRequest,
    session: DbSessionDep,
    settings: SettingsDep,
    user: AiUserDep,
) -> AiQueryResponse:
    service = AiQueryService(session, settings)
    return service.ask(
        tenant_id=user.tenant_id,
        question=body.question,
        allowed_doc_types=ai_allowed_doc_types(user),
    )
