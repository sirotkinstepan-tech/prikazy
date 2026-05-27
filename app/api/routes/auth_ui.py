from pathlib import Path

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import DbSessionDep, OptionalUserDep, SESSION_USER_ID_KEY
from app.auth.service import AuthService

router = APIRouter(tags=["auth"])

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/login")
def login_page(request: Request, user: OptionalUserDep):
    if user is not None:
        return RedirectResponse(
            url="/admin/" if user.is_admin else "/portal/",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": request.query_params.get("error")},
    )


@router.post("/login")
def login(
    request: Request,
    session: DbSessionDep,
    email: str = Form(),
    password: str = Form(),
):
    user = AuthService(session).authenticate(email, password)
    if user is None:
        return RedirectResponse(
            url="/login?error=invalid",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    request.session[SESSION_USER_ID_KEY] = str(user.id)
    return RedirectResponse(
        url="/admin/" if user.is_admin else "/portal/",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/")
def root(user: OptionalUserDep):
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if user.is_admin:
        return RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/portal/", status_code=status.HTTP_303_SEE_OTHER)
