from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.service import AuthenticatedUser
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.repositories.ai_usage import AiUsageRepository
from app.web.section_access import ai_access_mode


@dataclass(frozen=True)
class AiQuotaStatus:
    mode: str
    used: int | None = None
    limit: int | None = None
    remaining: int | None = None

    @property
    def is_unlimited(self) -> bool:
        return self.mode == "unlimited"


class AiUsageService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.repository = AiUsageRepository(session)

    def get_quota_status(self, user: AuthenticatedUser) -> AiQuotaStatus:
        mode = ai_access_mode(user)
        if mode == "none":
            return AiQuotaStatus(mode="none")
        if mode == "unlimited":
            return AiQuotaStatus(mode="unlimited")
        used = self.repository.count_user_queries_this_month(user.id)
        limit = self.settings.ai_monthly_query_limit
        return AiQuotaStatus(
            mode="limited",
            used=used,
            limit=limit,
            remaining=max(0, limit - used),
        )

    def consume_query(
        self,
        user: AuthenticatedUser,
        *,
        question: str | None = None,
    ) -> AiQuotaStatus:
        mode = ai_access_mode(user)
        if mode == "none":
            raise ApplicationError(
                "AI доступен при праве загрузки и скачивания в разделе "
                "или при «Полном доступе»",
                status_code=403,
                code="ai_access_denied",
            )
        if mode == "limited":
            used = self.repository.count_user_queries_this_month(user.id)
            limit = self.settings.ai_monthly_query_limit
            if used >= limit:
                raise ApplicationError(
                    f"Лимит AI-запросов исчерпан ({limit} в месяц). "
                    "Обратитесь к администратору для «Полного доступа».",
                    status_code=429,
                    code="ai_quota_exceeded",
                )
        preview = (question or "").strip()
        if len(preview) > 200:
            preview = preview[:197] + "..."
        self.repository.log_query(
            tenant_id=user.tenant_id,
            user_id=user.id,
            question_preview=preview or None,
        )
        return self.get_quota_status(user)
