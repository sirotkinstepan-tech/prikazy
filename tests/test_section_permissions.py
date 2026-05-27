from app.core.section_permissions import (
    access_for_doc_type,
    level_can_download,
    level_can_manage_document_links,
    level_can_upload,
    level_can_view,
    parse_section_access_level,
    resolve_access_for_role,
)
from app.models.enums import DocumentType, SectionAccessLevel, UserRole


def test_section_access_levels():
    assert level_can_view(SectionAccessLevel.VIEW_ONLY)
    assert not level_can_view(SectionAccessLevel.NONE)
    assert level_can_upload(SectionAccessLevel.UPLOAD_VIEW)
    assert not level_can_upload(SectionAccessLevel.VIEW_ONLY)
    assert level_can_download(SectionAccessLevel.VIEW_DOWNLOAD)
    assert not level_can_download(SectionAccessLevel.UPLOAD_VIEW)
    assert level_can_manage_document_links(SectionAccessLevel.FULL)
    assert level_can_manage_document_links(SectionAccessLevel.UPLOAD_VIEW)
    assert not level_can_manage_document_links(SectionAccessLevel.VIEW_ONLY)
    assert not level_can_manage_document_links(SectionAccessLevel.VIEW_DOWNLOAD)


def test_admin_has_full_access():
    access = resolve_access_for_role(UserRole.ADMIN, {})
    assert access[DocumentType.PRIKAZ.value] == SectionAccessLevel.FULL
    assert level_can_download(access_for_doc_type(access, DocumentType.PRIKAZ.value))


def test_parse_section_access():
    assert parse_section_access_level("view_only") == SectionAccessLevel.VIEW_ONLY
    assert parse_section_access_level(None) == SectionAccessLevel.NONE
