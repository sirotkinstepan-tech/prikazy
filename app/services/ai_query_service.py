from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.schemas.ai_query import AiQueryResponse, AiQuerySource
from app.services.ai_db_tools import (
    SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    AiDbToolExecutor,
    tool_result_content,
)
from app.services.llm_client import LlmClient, parse_tool_arguments


class AiQueryService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.llm_client = LlmClient(settings)

    def ask(self, *, tenant_id: UUID, question: str) -> AiQueryResponse:
        question = question.strip()
        if not question:
            raise ApplicationError(
                "Question must not be empty",
                status_code=400,
                code="empty_question",
            )

        executor = AiDbToolExecutor(self.session, tenant_id)
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        sources: list[AiQuerySource] = []

        for _ in range(self.settings.llm_max_tool_rounds):
            response = self.llm_client.chat_completion(messages=messages, tools=TOOL_DEFINITIONS)
            choice = response["choices"][0]["message"]
            tool_calls = choice.get("tool_calls") or []

            if not tool_calls:
                answer = (choice.get("content") or "").strip()
                if not answer:
                    raise ApplicationError(
                        "LLM returned empty answer",
                        status_code=502,
                        code="llm_empty_answer",
                    )
                return AiQueryResponse(answer=answer, sources=sources)

            messages.append(
                {
                    "role": "assistant",
                    "content": choice.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                function = tool_call["function"]
                tool_name = function["name"]
                arguments = parse_tool_arguments(function.get("arguments", "{}"))
                result = executor.execute(tool_name, arguments)
                sources.append(
                    AiQuerySource(
                        tool=tool_name,
                        arguments=arguments,
                        result_count=_result_count(result),
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": tool_result_content(result),
                    }
                )

        raise ApplicationError(
            "LLM exceeded maximum tool rounds without final answer",
            status_code=502,
            code="llm_max_rounds_exceeded",
        )


def _result_count(result: dict) -> int:
    if "total" in result:
        return int(result["total"])
    if "groups" in result:
        return len(result["groups"])
    if "field_names" in result:
        return len(result["field_names"])
    if "items" in result:
        return len(result["items"])
    return 0
