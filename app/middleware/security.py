import time
from collections import defaultdict
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        cutoff = now - window_seconds
        self._hits[key] = [stamp for stamp in bucket if stamp > cutoff]
        if len(self._hits[key]) >= limit:
            return False
        self._hits[key].append(now)
        return True

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        client = self._client_key(request)

        if path == "/login" and request.method == "POST":
            if not self._allow(
                f"login:{client}",
                limit=self.settings.rate_limit_login_per_minute,
                window_seconds=60,
            ):
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "rate_limited", "message": "Too many login attempts"}},
                )

        if path in {"/documents/upload", "/portal/upload", "/admin/upload"} and request.method == "POST":
            if not self._allow(
                f"upload:{client}",
                limit=self.settings.rate_limit_upload_per_minute,
                window_seconds=60,
            ):
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "rate_limited", "message": "Too many uploads"}},
                )

        return await call_next(request)
