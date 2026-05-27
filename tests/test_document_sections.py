import pytest

from app.core.document_sections import (
    resolve_doc_type_filters,
    validate_doc_type,
)
from app.core.errors import ApplicationError
from app.models.enums import DocumentType


def test_validate_doc_type_accepts_known_values():
    assert validate_doc_type("prikaz") == "prikaz"
    assert validate_doc_type("internal_contract") == "internal_contract"
    assert validate_doc_type("external_contract") == "external_contract"
    assert validate_doc_type("lna") == "lna"


def test_validate_doc_type_rejects_unknown_values():
    with pytest.raises(ApplicationError) as exc:
        validate_doc_type("invoice")
    assert exc.value.code == "invalid_doc_type"


def test_resolve_doc_type_filters_single():
    assert resolve_doc_type_filters(doc_type="lna", doc_types=None) == ["lna"]


def test_resolve_doc_type_filters_multiple():
    assert resolve_doc_type_filters(
        doc_type=None,
        doc_types=["prikaz", "lna"],
    ) == ["prikaz", "lna"]


def test_resolve_doc_type_filters_comma_separated():
    assert resolve_doc_type_filters(
        doc_type=None,
        doc_types=["prikaz,internal_contract"],
    ) == ["prikaz", "internal_contract"]


def test_resolve_doc_type_filters_prefers_doc_types():
    assert resolve_doc_type_filters(
        doc_type="prikaz",
        doc_types=["lna"],
    ) == ["lna"]


def test_resolve_doc_type_filters_none_for_all_sections():
    assert resolve_doc_type_filters(doc_type=None, doc_types=None) is None


def test_document_type_enum_values():
    assert {item.value for item in DocumentType} == {
        "prikaz",
        "internal_contract",
        "external_contract",
        "lna",
    }
