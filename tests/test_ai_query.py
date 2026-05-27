from datetime import date
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.models.enums import AccessLevel
from app.repositories.ai_query import AiQueryRepository
from app.services.ai_db_tools import AiDbToolExecutor
from app.services.ai_query_service import AiQueryService
from app.services.auth_service import AuthService, AuthenticatedUser
from app.services.llm_client import LlmClient, _from_yandex_response, _to_yandex_messages


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


def test_find_by_extracted_field_filters_by_tenant_and_field():
    session = FakeSession(
        responses=[
            FakeResult(scalar=2),
            FakeResult(
                rows=[
                    {
                        "document_id": uuid4(),
                        "created_at": date.today(),
                        "status": "processed",
                        "doc_type": "order",
                        "document_date": None,
                        "counterparty_name": None,
                        "title": "Приказ 1",
                        "field_name": "ответственный",
                        "field_value": "Иванов",
                    }
                ]
            ),
        ]
    )
    repository = AiQueryRepository(session)
    tenant_id = uuid4()

    items, total = repository.find_by_extracted_field(
        tenant_id=tenant_id,
        field_name="ответственный",
        field_value="Иванов",
    )

    count_sql, params = session.calls[0]
    assert total == 2
    assert len(items) == 1
    assert "d.tenant_id = :tenant_id" in count_sql
    assert "ef.field_name ILIKE :field_name" in count_sql
    assert "ef.field_value ILIKE :field_value" in count_sql
    assert params["tenant_id"] == tenant_id
    assert params["field_name"] == "%ответственный%"
    assert params["field_value"] == "%Иванов%"


def test_group_documents_uses_allowed_group_by():
    session = FakeSession(
        responses=[
            FakeResult(
                rows=[
                    {"group_key": "order", "document_count": 5},
                    {"group_key": "memo", "document_count": 2},
                ]
            )
        ]
    )
    repository = AiQueryRepository(session)
    tenant_id = uuid4()

    groups = repository.group_documents(tenant_id=tenant_id, group_by="doc_type")

    sql, params = session.calls[0]
    assert len(groups) == 2
    assert "GROUP BY group_key" in sql
    assert params["tenant_id"] == tenant_id


def test_group_documents_rejects_unknown_group_by():
    repository = AiQueryRepository(FakeSession())
    with pytest.raises(ValueError, match="Unsupported group_by"):
        repository.group_documents(tenant_id=uuid4(), group_by="invalid")


def test_tool_executor_search_documents():
    session = FakeSession(
        responses=[
            FakeResult(scalar=1),
            FakeResult(
                rows=[
                    {
                        "document_id": uuid4(),
                        "status": "processed",
                        "doc_type": "order",
                        "document_date": None,
                        "counterparty_name": None,
                        "rank": 0.8,
                        "snippet": "приказ о ...",
                    }
                ]
            ),
        ]
    )
    executor = AiDbToolExecutor(session, uuid4())
    result = executor.execute("search_documents", {"query": "приказ", "limit": 10})

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["snippet"] == "приказ о ..."


class FakeLlmClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.is_configured = True

    def chat_completion(self, *, messages, tools=None):
        response = self.responses[self.calls]
        self.calls += 1
        return response


def test_ai_query_service_tool_loop_and_final_answer():
    session = FakeSession(
        responses=[
            FakeResult(scalar=1),
            FakeResult(
                rows=[
                    {
                        "document_id": uuid4(),
                        "status": "processed",
                        "doc_type": "order",
                        "document_date": None,
                        "counterparty_name": None,
                        "rank": 0.5,
                        "snippet": "ответственный: Петров",
                    }
                ]
            ),
        ]
    )
    settings = Settings(yandex_api_key="test-key", yandex_folder_id="folder", llm_max_tool_rounds=3)
    service = AiQueryService(session, settings)
    service.llm_client = FakeLlmClient(
        [
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_documents",
                                        "arguments": '{"query":"Петров"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "content": "Найден 1 приказ, где упоминается Петров.",
                            "tool_calls": [],
                        }
                    }
                ]
            },
        ]
    )

    response = service.ask(
        tenant_id=uuid4(),
        question="Какие приказы связаны с Петровым?",
    )

    assert "Петров" in response.answer
    assert len(response.sources) == 1
    assert response.sources[0].tool == "search_documents"


def test_ai_query_service_rejects_empty_question():
    service = AiQueryService(
        FakeSession(),
        Settings(yandex_api_key="test-key", yandex_folder_id="folder"),
    )
    service.llm_client = FakeLlmClient([])

    with pytest.raises(ApplicationError) as exc_info:
        service.ask(tenant_id=uuid4(), question="   ")

    assert exc_info.value.code == "empty_question"


def test_yandex_message_conversion_for_tool_results():
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "question"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "search_documents",
                    "type": "function",
                    "function": {"name": "search_documents", "arguments": '{"query":"test"}'},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "search_documents",
            "name": "search_documents",
            "content": '{"total": 0, "items": []}',
        },
    ]

    converted = _to_yandex_messages(messages)

    assert converted[0]["role"] == "system"
    assert converted[-1]["toolResultList"]["toolResults"][0]["functionResult"]["name"] == "search_documents"


def test_yandex_response_normalization():
    raw = {
        "result": {
            "alternatives": [
                {
                    "message": {
                        "role": "assistant",
                        "text": "Ответ из базы",
                    }
                }
            ]
        }
    }

    normalized = _from_yandex_response(raw)

    assert normalized["choices"][0]["message"]["content"] == "Ответ из базы"


def test_llm_client_yandex_is_configured():
    client = LlmClient(
        Settings(
            llm_provider="yandex",
            yandex_api_key="key",
            yandex_folder_id="folder",
        )
    )
    assert client.is_configured is True


def test_auth_requires_full_access_for_ai():
    tenant_id = uuid4()
    user = AuthenticatedUser(
        user_id=uuid4(),
        tenant_id=tenant_id,
        name="Reader",
        access_level=AccessLevel.READ,
    )

    with pytest.raises(ApplicationError) as exc_info:
        AuthService(FakeSession()).require_full_access(user, tenant_id)

    assert exc_info.value.code == "insufficient_permissions"


def test_access_level_full_access_label():
    assert AccessLevel.FULL_ACCESS.label == "Полный доступ"
