"""Schema definitions for the STR Assistant API."""

from typing import Any, Literal, NotRequired

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class UserInput(BaseModel):
    message: str = Field(description="User input message.")
    thread_id: str | None = Field(default=None)
    session_id: str | None = Field(default=None)
    user_id: str | None = Field(default=None)


class StreamRequest(UserInput):
    stream_tokens: bool = Field(default=True)


class ToolCall(TypedDict):
    name: str
    args: dict[str, Any]
    id: str | None
    type: NotRequired[Literal["tool_call"]]


class ChatMessage(BaseModel):
    type: Literal["human", "ai", "tool", "custom"] = Field(description="Message type.")
    content: str = Field(description="Message content.")
    tool_calls: list[ToolCall] = Field(default=[])
    tool_call_id: str | None = Field(default=None)
    run_id: str | None = Field(default=None)
    thread_id: str | None = Field(default=None)
    session_id: str | None = Field(default=None)
    ai_call_id: str | None = Field(default=None)
    response_metadata: dict[str, Any] = Field(default={})
    custom_data: dict[str, Any] = Field(default={})


class FeedbackRequest(BaseModel):
    run_id: str
    key: str
    score: float
    kwargs: dict[str, Any] = Field(default={})


class FeedbackResponse(BaseModel):
    status: Literal["success"] = "success"


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessage]
