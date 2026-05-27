from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ApplicationError
from app.models.enums import AccessLevel
from app.repositories.users import UserRepository


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    tenant_id: UUID
    name: str
    access_level: AccessLevel


class AuthService:
    def __init__(self, session: Session):
        self.repository = UserRepository(session)

    def authenticate(self, raw_token: str) -> AuthenticatedUser:
        token = self.repository.get_active_token(raw_token.strip())
        if token is None:
            raise ApplicationError(
                "Invalid or expired API token",
                status_code=401,
                code="invalid_token",
            )
        self.repository.touch_token(token)
        return AuthenticatedUser(
            user_id=token.user.id,
            tenant_id=token.user.tenant_id,
            name=token.user.name,
            access_level=AccessLevel(token.user.access_level),
        )

    def require_full_access(self, user: AuthenticatedUser, tenant_id: UUID) -> None:
        if user.tenant_id != tenant_id:
            raise ApplicationError(
                "Token tenant does not match requested tenant_id",
                status_code=403,
                code="tenant_mismatch",
            )
        if user.access_level is not AccessLevel.FULL_ACCESS:
            raise ApplicationError(
                "AI queries require «Полный доступ» permission",
                status_code=403,
                code="insufficient_permissions",
            )
