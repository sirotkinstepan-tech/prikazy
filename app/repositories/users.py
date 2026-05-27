from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.models.api_token import ApiToken
from app.models.enums import AccessLevel
from app.models.user import User
from app.services.llm_client import generate_api_token, hash_api_token


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_active_token(self, raw_token: str) -> ApiToken | None:
        token_hash = hash_api_token(raw_token)
        token = self.session.scalars(
            select(ApiToken)
            .options(joinedload(ApiToken.user))
            .where(ApiToken.token_hash == token_hash)
        ).first()
        if token is None:
            return None
        if token.expires_at is not None and token.expires_at <= datetime.now(UTC):
            return None
        if not token.user.is_active:
            return None
        return token

    def touch_token(self, token: ApiToken) -> None:
        self.session.execute(
            update(ApiToken)
            .where(ApiToken.id == token.id)
            .values(last_used_at=datetime.now(UTC))
        )

    def create_user_with_token(
        self,
        *,
        tenant_id: UUID,
        name: str,
        access_level: AccessLevel,
        email: str | None = None,
        token_name: str = "default",
    ) -> tuple[User, str]:
        user = User(
            tenant_id=tenant_id,
            name=name,
            email=email,
            access_level=access_level.value,
            is_active=True,
        )
        raw_token = generate_api_token()
        api_token = ApiToken(
            user=user,
            token_hash=hash_api_token(raw_token),
            name=token_name,
        )
        self.session.add(user)
        self.session.add(api_token)
        self.session.flush()
        return user, raw_token
