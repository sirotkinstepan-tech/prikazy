from app.api.http_utils import build_content_disposition


def test_build_content_disposition_encodes_unicode_filename():
    header = build_content_disposition("attachment", 'Приказ №1 "срочно".pdf')
    assert header.startswith('attachment; filename="')
    assert "filename*=UTF-8''" in header
