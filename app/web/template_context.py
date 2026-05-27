from fastapi import Request

from app.security.csrf import csrf_context


def web_template_context(request: Request, **extra) -> dict:
    return {**csrf_context(request), **extra}
