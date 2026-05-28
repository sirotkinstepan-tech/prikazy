from uuid import uuid4

from app.models.enums import DocumentType
from app.services.ai_db_tools import AiDbToolExecutor


class FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        return self

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])
        self._index = 0

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        if self._index < len(self.responses):
            response = self.responses[self._index]
            self._index += 1
            return response
        return FakeResult(scalar=0, rows=[])


def test_search_documents_restricts_to_allowed_doc_types_in_sql():
    session = FakeSession(
        responses=[
            FakeResult(scalar=0),
            FakeResult(rows=[]),
        ]
    )
    executor = AiDbToolExecutor(
        session,
        uuid4(),
        allowed_doc_types=[DocumentType.PRIKAZ.value],
    )
    executor.execute("search_documents", {"query": "Сбер"})

    _, params = session.calls[0]
    assert params["doc_types"] == [DocumentType.PRIKAZ.value]


def test_search_documents_denies_explicit_forbidden_doc_type():
    session = FakeSession()
    executor = AiDbToolExecutor(
        session,
        uuid4(),
        allowed_doc_types=[DocumentType.PRIKAZ.value],
    )
    result = executor.execute(
        "search_documents",
        {"query": "договор", "doc_type": DocumentType.EXTERNAL_CONTRACT.value},
    )
    assert result == {"total": 0, "returned": 0, "truncated": False, "items": []}
    assert session.calls == []


def test_search_documents_filters_rows_from_other_sections():
    session = FakeSession(
        responses=[
            FakeResult(scalar=2),
            FakeResult(
                rows=[
                    {
                        "document_id": uuid4(),
                        "doc_type": DocumentType.PRIKAZ.value,
                        "title": "Приказ",
                        "rank": 1.0,
                        "snippet": "текст",
                    },
                    {
                        "document_id": uuid4(),
                        "doc_type": DocumentType.EXTERNAL_CONTRACT.value,
                        "title": "Сбер",
                        "rank": 0.9,
                        "snippet": "текст",
                    },
                ]
            ),
        ]
    )
    executor = AiDbToolExecutor(
        session,
        uuid4(),
        allowed_doc_types=[DocumentType.PRIKAZ.value],
    )
    result = executor.execute("search_documents", {"query": "договор", "doc_type": DocumentType.PRIKAZ.value})
    assert result["total"] == 2
    assert result["returned"] == 1
    assert result["truncated"] is True
    assert result["items"][0]["doc_type"] == DocumentType.PRIKAZ.value


def test_group_documents_restricts_counts_to_allowed_sections():
    session = FakeSession(
        responses=[
            FakeResult(
                rows=[
                    {"group_key": "processed", "document_count": 2},
                ]
            )
        ]
    )
    executor = AiDbToolExecutor(
        session,
        uuid4(),
        allowed_doc_types=[DocumentType.PRIKAZ.value],
    )
    executor.execute("group_documents", {"group_by": "status"})

    _, params = session.calls[0]
    assert params["doc_types"] == [DocumentType.PRIKAZ.value]


def test_group_documents_excludes_archived_documents_in_sql():
    session = FakeSession(
        responses=[
            FakeResult(
                rows=[
                    {"group_key": "processed", "document_count": 3},
                ]
            )
        ]
    )
    executor = AiDbToolExecutor(session, uuid4())
    result = executor.execute("group_documents", {"group_by": "status"})

    sql, _ = session.calls[0]
    assert "d.archived_at IS NULL" in sql
    assert result["grand_total"] == 3
    assert result["group_count"] == 1


def test_list_field_names_restricts_to_allowed_sections():
    session = FakeSession(responses=[FakeResult(rows=[])])
    executor = AiDbToolExecutor(
        session,
        uuid4(),
        allowed_doc_types=[DocumentType.PRIKAZ.value],
    )
    executor.execute("list_field_names", {})

    _, params = session.calls[0]
    assert params["doc_types"] == [DocumentType.PRIKAZ.value]
