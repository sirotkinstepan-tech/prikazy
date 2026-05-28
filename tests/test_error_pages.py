from app.core.errors import ApplicationError
from app.web.error_pages import _wants_html_response, build_application_error_response


class FakeURL:
    def __init__(self, path: str):
        self.path = path


class FakeRequest:
    def __init__(self, path: str, accept: str = "text/html"):
        self.url = FakeURL(path)
        self.headers = {"accept": accept}


def test_wants_html_for_portal_and_admin_paths():
    assert _wants_html_response(FakeRequest("/portal/documents"))
    assert _wants_html_response(FakeRequest("/admin/users"))


def test_portal_application_error_returns_html():
    request = FakeRequest("/portal/documents?section=prikaz")
    exc = ApplicationError(
        "Нет доступа к этому разделу",
        status_code=403,
        code="section_access_denied",
    )
    response = build_application_error_response(request, exc)
    assert response.status_code == 403
    assert "text/html" in response.headers.get("content-type", "")
    assert "Нет доступа к разделу" in response.body.decode()
