from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.ai_query_log import AiQueryLog


class AiUsageRepository:
    def __init__(self, session: Session):
        self.session = session

    def count_user_queries_this_month(self, user_id: UUID) -> int:
        sql = text(
            """
            SELECT count(*) AS total
            FROM ai_query_logs
            WHERE user_id = :user_id
              AND created_at >= date_trunc('month', now())
            """
        )
        return int(self.session.execute(sql, {"user_id": user_id}).scalar_one())

    def log_query(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        question_preview: str | None = None,
    ) -> AiQueryLog:
        entry = AiQueryLog(
            tenant_id=tenant_id,
            user_id=user_id,
            question_preview=question_preview,
        )
        self.session.add(entry)
        self.session.flush()
        return entry
