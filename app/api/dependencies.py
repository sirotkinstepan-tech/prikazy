from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.service import AuthService, AuthenticatedUser
from app.core.config import Settings, get_settings
from app.core.errors import AuthRedirect
from app.db.session import get_db_session
from app.models.enums import UserRole
from app.security.csrf import verify_csrf_header

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[Session, Depends(get_db_session)]

SESSION_USER_ID_KEY = "user_id"


def _load_user(request: Request, session: Session) -> AuthenticatedUser | None:
    raw_user_id = request.session.get(SESSION_USER_ID_KEY)
    if not raw_user_id:
        return None
    try:
        user_id = UUID(str(raw_user_id))
    except ValueError:
        return None
    return AuthService(session).get_user(user_id)


def get_current_user(request: Request, session: DbSessionDep) -> AuthenticatedUser:
    user = _load_user(request, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_optional_user(request: Request, session: DbSessionDep) -> AuthenticatedUser | None:
    return _load_user(request, session)


def require_admin(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_web_user(request: Request, session: DbSessionDep) -> AuthenticatedUser:
    user = _load_user(request, session)
    if user is None:
        raise AuthRedirect("/login")
    return user


def require_web_admin(user: Annotated[AuthenticatedUser, Depends(require_web_user)]) -> AuthenticatedUser:
    if user.role != UserRole.ADMIN:
        raise AuthRedirect("/portal/")
    return user


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
OptionalUserDep = Annotated[AuthenticatedUser | None, Depends(get_optional_user)]
AdminUserDep = Annotated[AuthenticatedUser, Depends(require_admin)]
WebUserDep = Annotated[AuthenticatedUser, Depends(require_web_user)]
WebAdminDep = Annotated[AuthenticatedUser, Depends(require_web_admin)]
CsrfHeaderDep = Annotated[None, Depends(verify_csrf_header)]
