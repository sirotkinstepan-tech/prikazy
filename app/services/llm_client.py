import hashlib
import json
import secrets
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.errors import ApplicationError

YANDEX_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class LlmClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        if self.settings.llm_provider == "yandex":
            return bool(
                self.settings.yandex_api_key.strip() and self.settings.yandex_folder_id.strip()
            )
        return bool(self.settings.llm_api_key.strip())

    def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise ApplicationError(
                "LLM API is not configured. Set Yandex Cloud credentials in environment.",
                status_code=503,
                code="llm_not_configured",
            )
        if self.settings.llm_provider == "yandex":
            return self._yandex_chat_completion(messages=messages, tools=tools)
        return self._openai_chat_completion(messages=messages, tools=tools)

    def _openai_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        url = f"{self.settings.llm_api_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        return self._post_json(url, headers, payload)

    def _yandex_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        folder_id = self.settings.yandex_folder_id.strip()
        model = self.settings.yandex_model.strip()
        payload: dict[str, Any] = {
            "modelUri": f"gpt://{folder_id}/{model}",
            "completionOptions": {
                "stream": False,
                "temperature": 0,
                "maxTokens": str(self.settings.llm_max_output_tokens),
            },
            "messages": _to_yandex_messages(messages),
        }
        if tools:
            payload["tools"] = [_to_yandex_tool(tool) for tool in tools]

        headers = {
            "Authorization": f"Api-Key {self.settings.yandex_api_key.strip()}",
            "Content-Type": "application/json",
            "x-folder-id": folder_id,
        }
        raw = self._post_json(YANDEX_COMPLETION_URL, headers, payload)
        return _from_yandex_response(raw)

    def _post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                "LLM request timed out",
                status_code=504,
                code="llm_timeout",
            ) from exc
        except httpx.HTTPError as exc:
            raise ApplicationError(
                f"LLM request failed: {exc}",
                status_code=502,
                code="llm_request_failed",
            ) from exc

        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise ApplicationError(
                f"LLM API error ({response.status_code}): {detail}",
                status_code=502,
                code="llm_api_error",
            )
        return response.json()


def parse_tool_arguments(raw_arguments: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    return json.loads(raw_arguments)


def _to_yandex_tool(tool: dict[str, Any]) -> dict[str, Any]:
    if tool.get("type") == "function" and "function" in tool:
        return {"function": tool["function"]}
    return tool


def _to_yandex_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    yandex_messages: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role in {"system", "user"} and "content" in message:
            yandex_messages.append({"role": role, "text": message["content"]})
            continue
        if role == "assistant":
            if message.get("tool_calls"):
                tool_calls = []
                for tool_call in message["tool_calls"]:
                    function = tool_call["function"]
                    tool_calls.append(
                        {
                            "functionCall": {
                                "name": function["name"],
                                "arguments": parse_tool_arguments(function.get("arguments", "{}")),
                            }
                        }
                    )
                yandex_messages.append({"role": "assistant", "toolCallList": {"toolCalls": tool_calls}})
                continue
            if message.get("content"):
                yandex_messages.append({"role": "assistant", "text": message["content"]})
                continue
        if role == "tool":
            tool_results = [
                {
                    "functionResult": {
                        "name": message.get("name") or message.get("tool_call_id", "tool"),
                        "content": message["content"],
                    }
                }
            ]
            yandex_messages.append({"role": "user", "toolResultList": {"toolResults": tool_results}})
    return yandex_messages


def _from_yandex_response(raw: dict[str, Any]) -> dict[str, Any]:
    message = raw["result"]["alternatives"][0]["message"]
    normalized_message: dict[str, Any] = {"role": "assistant"}
    if "text" in message:
        normalized_message["content"] = message["text"]
        normalized_message["tool_calls"] = []
    elif "toolCallList" in message:
        normalized_message["content"] = None
        normalized_message["tool_calls"] = []
        for index, tool_call in enumerate(message["toolCallList"]["toolCalls"], start=1):
            function_call = tool_call["functionCall"]
            normalized_message["tool_calls"].append(
                {
                    "id": function_call["name"] or f"call_{index}",
                    "type": "function",
                    "function": {
                        "name": function_call["name"],
                        "arguments": json.dumps(function_call.get("arguments", {}), ensure_ascii=False),
                    },
                }
            )
    else:
        normalized_message["content"] = ""
        normalized_message["tool_calls"] = []
    return {"choices": [{"message": normalized_message}]}


def hash_api_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_api_token() -> str:
    return secrets.token_urlsafe(32)
