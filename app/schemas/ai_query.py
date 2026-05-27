from typing import Any

from pydantic import BaseModel, Field


class AiQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AiQuerySource(BaseModel):
    tool: str
    arguments: dict[str, Any]
    result_count: int


class AiQueryResponse(BaseModel):
    answer: str
    sources: list[AiQuerySource]
