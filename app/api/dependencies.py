from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApplicationError
from app.db.session import get_db_session
from app.models.enums import AccessLevel
from app.services.auth_service import AuthService, AuthenticatedUser

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[Session, Depends(get_db_session)]

_bearer_scheme = HTTPBearer(auto_error=False)


def _extract_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str | None:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if x_api_key:
        return x_api_key.strip()
    return None


def get_current_user(
    session: DbSessionDep,
    raw_token: Annotated[str | None, Depends(_extract_bearer_token)],
) -> AuthenticatedUser:
    if not raw_token:
        raise ApplicationError(
            "Authorization required. Provide Bearer token or X-API-Key header.",
            status_code=401,
            code="missing_token",
        )
    return AuthService(session).authenticate(raw_token)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_full_access_user(
    session: DbSessionDep,
    settings: SettingsDep,
    tenant_id: UUID,
    raw_token: Annotated[str | None, Depends(_extract_bearer_token)],
) -> AuthenticatedUser:
    if not settings.auth_required_for_ai:
        return AuthenticatedUser(
            user_id=UUID(int=0),
            tenant_id=tenant_id,
            name="dev-bypass",
            access_level=AccessLevel.FULL_ACCESS,
        )
    if not raw_token:
        raise ApplicationError(
            "Authorization required. Provide Bearer token or X-API-Key header.",
            status_code=401,
            code="missing_token",
        )
    user = AuthService(session).authenticate(raw_token)
    AuthService(session).require_full_access(user, tenant_id)
    return user


FullAccessUserDep = Annotated[AuthenticatedUser, Depends(require_full_access_user)]
