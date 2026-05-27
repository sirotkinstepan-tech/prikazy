import secrets

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings

CSRF_SESSION_KEY = "csrf_token"


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def csrf_context(request: Request) -> dict[str, str]:
    return {"csrf_token": ensure_csrf_token(request)}


def rotate_csrf_token(request: Request) -> str:
    token = secrets.token_urlsafe(32)
    request.session[CSRF_SESSION_KEY] = token
    return token


def _expected_token(request: Request) -> str | None:
    return request.session.get(CSRF_SESSION_KEY)


def verify_csrf_token(request: Request, provided: str | None) -> None:
    if not get_settings().csrf_enabled:
        return
    expected = _expected_token(request)
    if not expected or not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )


def verify_csrf_form(request: Request, csrf_token: str) -> None:
    verify_csrf_token(request, csrf_token)


def verify_csrf_header(
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    verify_csrf_token(request, x_csrf_token)
