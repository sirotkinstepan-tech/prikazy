from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "application_error"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class AuthRedirect(Exception):
    def __init__(self, url: str):
        self.url = url


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthRedirect)
    async def auth_redirect_handler(_request: Request, exc: AuthRedirect):
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url=exc.url, status_code=303)

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        _request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
