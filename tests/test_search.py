from uuid import uuid4

from app.repositories.search import SearchRepository


class FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        if len(self.calls) == 1:
            return FakeResult(scalar=1)
        return FakeResult(
            rows=[
                {
                    "document_id": uuid4(),
                    "status": "processed",
                    "doc_type": "invoice",
                    "document_date": None,
                    "counterparty_name": "ACME",
                    "rank": 0.5,
                    "snippet": "ACME invoice",
                }
            ]
        )


def test_search_query_uses_postgresql_full_text_and_filters():
    session = FakeSession()
    repository = SearchRepository(session)

    items, total = repository.search(
        tenant_id=uuid4(),
        query="acme invoice",
        doc_type="invoice",
        status="processed",
        counterparty_name="ACME",
    )

    count_sql, params = session.calls[0]
    items_sql, _ = session.calls[1]
    assert total == 1
    assert len(items) == 1
    assert "websearch_to_tsquery('simple', :query)" in count_sql
    assert "ts_rank(lor.search_vector, q.tsq)" in items_sql
    assert "d.doc_type = :doc_type" in items_sql
    assert params["counterparty_name"] == "%ACME%"
