import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.document_sections import resolve_doc_type_slug
from app.core.errors import ApplicationError
from app.repositories.ai_query import AiQueryRepository
from app.repositories.documents import DocumentRepository
from app.repositories.search import SearchRepository
from app.services.llm_client import parse_tool_arguments

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Полнотекстовый поиск по OCR-тексту документов (приказов). "
                "Используй для поиска по содержимому, ключевым словам, фразам."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "doc_type": {"type": "string", "description": "Тип документа"},
                    "status": {
                        "type": "string",
                        "description": "Статус: uploaded, processed, validated, failed, archived",
                    },
                    "counterparty_name": {"type": "string", "description": "Контрагент"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": (
                "Список документов по метаданным: тип, статус, дата, контрагент. "
                "Без полнотекстового поиска. "
                "Поле total — общее число документов по фильтрам; returned — сколько строк в items (limit)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {"type": "string"},
                    "status": {"type": "string"},
                    "counterparty_name": {"type": "string"},
                    "document_date_from": {"type": "string", "format": "date"},
                    "document_date_to": {"type": "string", "format": "date"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_by_extracted_field",
            "description": (
                "Поиск документов по извлечённым полям OCR "
                "(ответственный, номер приказа, подразделение и т.д.). "
                "Для ответственного используй field_name='ответственный' или похожие имена."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "Имя поля, например: ответственный, номер, подразделение",
                    },
                    "field_value": {
                        "type": "string",
                        "description": "Значение поля (частичное совпадение)",
                    },
                    "doc_type": {"type": "string"},
                    "status": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "group_documents",
            "description": (
                "Группировка документов: количество по типу, статусу, контрагенту или месяцу даты. "
                "Для общего числа документов используй grand_total (сумма по группам)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "group_by": {
                        "type": "string",
                        "enum": [
                            "doc_type",
                            "status",
                            "counterparty_name",
                            "document_date_month",
                        ],
                    },
                    "doc_type": {"type": "string"},
                    "status": {"type": "string"},
                    "document_date_from": {"type": "string", "format": "date"},
                    "document_date_to": {"type": "string", "format": "date"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                },
                "required": ["group_by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_field_names",
            "description": (
                "Список имён извлечённых полей в базе. "
                "Полезно, чтобы узнать как называется поле «ответственный» и т.п."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name_pattern": {
                        "type": "string",
                        "description": "Фильтр по части имени поля",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                },
            },
        },
    },
]

SYSTEM_PROMPT = """\
Ты — ассистент для работы с базой документов «приказы».

СТРОГИЕ ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе данных из инструментов базы данных.
2. НЕ используй интернет и внешние знания — только результаты инструментов.
3. Перед ответом ОБЯЗАТЕЛЬНО вызови нужные инструменты.
4. Если данных нет — честно скажи об этом.
5. Отвечай на том же языке, что и вопрос пользователя.

Подсчёт документов:
- «Сколько всего документов» → group_documents (group_by=status или doc_type), бери grand_total.
- search_documents.total — только совпадения с текстовым запросом, не общее число в базе.
- list_documents.total — общее число по фильтрам; returned/items — только текущая страница (limit).
- doc_type передавай slug: prikaz, lna, external_contract, incoming_correspondence и т.д.

О домене:
- Документы — приказы, договоры, ЛНА, корреспонденция и другие разделы.
- Ответственные, номера, подразделения могут храниться в extracted_fields.
- Для «какие приказы у ответственного X» используй find_by_extracted_field.
- Для «группы приказов» / «сколько по типам» используй group_documents.
- Для поиска по тексту приказа используй search_documents.
"""


def _serialize_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _serialize_value(val) for key, val in row.items()}


def _serialize_document(document) -> dict[str, Any]:
    return {
        "document_id": str(document.id),
        "created_at": document.created_at.isoformat(),
        "status": document.status,
        "doc_type": document.doc_type,
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "counterparty_name": document.counterparty_name,
        "title": document.title,
        "source_filename": document.source_filename,
    }


class AiDbToolExecutor:
    def __init__(
        self,
        session: Session,
        tenant_id: UUID,
        allowed_doc_types: list[str] | None = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.allowed_doc_types = allowed_doc_types
        self.search_repository = SearchRepository(session)
        self.document_repository = DocumentRepository(session)
        self.ai_query_repository = AiQueryRepository(session)

    def _doc_type_allowed(self, doc_type: str | None) -> bool:
        if not doc_type or self.allowed_doc_types is None:
            return True
        return doc_type in self.allowed_doc_types

    @staticmethod
    def _pack_list_result(total: int, serialized: list[dict[str, Any]]) -> dict[str, Any]:
        returned = len(serialized)
        return {
            "total": int(total),
            "returned": returned,
            "truncated": returned < int(total),
            "items": serialized,
        }

    def _resolve_doc_type_filters(
        self, params: dict[str, Any]
    ) -> tuple[str | None, list[str] | None, bool]:
        requested = resolve_doc_type_slug(params.get("doc_type"))
        if requested:
            if not self._doc_type_allowed(requested):
                return None, None, True
            return requested, None, False

        if self.allowed_doc_types is not None:
            if not self.allowed_doc_types:
                return None, None, True
            return None, self.allowed_doc_types, False

        return None, None, False

    @staticmethod
    def _empty_search_result() -> dict[str, Any]:
        return {"total": 0, "returned": 0, "truncated": False, "items": []}

    def _filter_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.allowed_doc_types is None:
            return rows
        return [row for row in rows if row.get("doc_type") in self.allowed_doc_types]

    def _filter_documents(self, documents) -> list:
        if self.allowed_doc_types is None:
            return documents
        return [doc for doc in documents if doc.doc_type in self.allowed_doc_types]

    def execute(self, tool_name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
        params = parse_tool_arguments(arguments)
        handlers = {
            "search_documents": self._search_documents,
            "list_documents": self._list_documents,
            "find_by_extracted_field": self._find_by_extracted_field,
            "group_documents": self._group_documents,
            "list_field_names": self._list_field_names,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            raise ApplicationError(
                f"Unknown tool: {tool_name}",
                status_code=400,
                code="unknown_tool",
            )
        return handler(params)

    def _search_documents(self, params: dict[str, Any]) -> dict[str, Any]:
        query = params.get("query", "").strip()
        if not query:
            raise ApplicationError(
                "search_documents requires non-empty query",
                status_code=400,
                code="invalid_tool_arguments",
            )
        limit = min(int(params.get("limit", 20)), 50)
        doc_type, doc_types, denied = self._resolve_doc_type_filters(params)
        if denied:
            return self._empty_search_result()
        items, total = self.search_repository.search(
            tenant_id=self.tenant_id,
            query=query,
            doc_type=doc_type,
            doc_types=doc_types,
            status=params.get("status"),
            counterparty_name=params.get("counterparty_name"),
            limit=limit,
            offset=0,
        )
        filtered = self._filter_rows(items)
        serialized = [_serialize_row(item) for item in filtered]
        returned = len(serialized)
        return {
            "total": int(total),
            "returned": returned,
            "truncated": returned < int(total),
            "items": serialized,
        }

    def _list_documents(self, params: dict[str, Any]) -> dict[str, Any]:
        limit = min(int(params.get("limit", 20)), 50)
        doc_type, doc_types, denied = self._resolve_doc_type_filters(params)
        if denied:
            return {"total": 0, "items": []}
        items, total = self.document_repository.list_for_tenant(
            tenant_id=self.tenant_id,
            doc_type=doc_type,
            doc_types=doc_types,
            status=params.get("status"),
            counterparty_name=params.get("counterparty_name"),
            document_date_from=_parse_date(params.get("document_date_from")),
            document_date_to=_parse_date(params.get("document_date_to")),
            limit=limit,
            offset=0,
        )
        filtered = self._filter_documents(items)
        serialized = [_serialize_document(doc) for doc in filtered]
        return self._pack_list_result(total, serialized)

    def _find_by_extracted_field(self, params: dict[str, Any]) -> dict[str, Any]:
        limit = min(int(params.get("limit", 20)), 50)
        doc_type, doc_types, denied = self._resolve_doc_type_filters(params)
        if denied:
            return {"total": 0, "items": []}
        items, total = self.ai_query_repository.find_by_extracted_field(
            tenant_id=self.tenant_id,
            field_name=params.get("field_name"),
            field_value=params.get("field_value"),
            doc_type=doc_type,
            doc_types=doc_types,
            status=params.get("status"),
            limit=limit,
            offset=0,
        )
        filtered = self._filter_rows(items)
        serialized = [_serialize_row(item) for item in filtered]
        return self._pack_list_result(total, serialized)

    def _group_documents(self, params: dict[str, Any]) -> dict[str, Any]:
        group_by = params.get("group_by")
        if not group_by:
            raise ApplicationError(
                "group_documents requires group_by",
                status_code=400,
                code="invalid_tool_arguments",
            )
        limit = min(int(params.get("limit", 50)), 100)
        doc_type, doc_types, denied = self._resolve_doc_type_filters(params)
        if denied:
            return {"groups": [], "group_by": group_by, "group_count": 0, "grand_total": 0}
        try:
            groups = self.ai_query_repository.group_documents(
                tenant_id=self.tenant_id,
                group_by=group_by,
                doc_type=doc_type,
                doc_types=doc_types,
                status=params.get("status"),
                document_date_from=_parse_date(params.get("document_date_from")),
                document_date_to=_parse_date(params.get("document_date_to")),
                limit=limit,
            )
        except ValueError as exc:
            raise ApplicationError(
                str(exc),
                status_code=400,
                code="invalid_tool_arguments",
            ) from exc
        if group_by == "doc_type":
            groups = [group for group in groups if self._doc_type_allowed(group.get("group_key"))]
        serialized = [_serialize_row(group) for group in groups]
        grand_total = sum(int(group.get("document_count", 0)) for group in groups)
        return {
            "groups": serialized,
            "group_by": group_by,
            "group_count": len(serialized),
            "grand_total": grand_total,
        }

    def _list_field_names(self, params: dict[str, Any]) -> dict[str, Any]:
        limit = min(int(params.get("limit", 50)), 100)
        _, doc_types, denied = self._resolve_doc_type_filters(params)
        if denied:
            return {"field_names": [], "total": 0}
        names = self.ai_query_repository.list_distinct_field_names(
            tenant_id=self.tenant_id,
            name_pattern=params.get("name_pattern"),
            doc_types=doc_types,
            limit=limit,
        )
        return {"field_names": names, "total": len(names)}


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


def tool_result_content(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)
