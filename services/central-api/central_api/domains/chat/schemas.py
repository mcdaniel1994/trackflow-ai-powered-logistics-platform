"""Authenticated HTTP contracts for Phase 4 chat-session history."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ChatSessionRead(ChatAPIModel):
    session_id: str
    agent_id: str
    user_id: str
    client_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class ChatMessageRead(ChatAPIModel):
    message_id: str
    session_id: str
    role: str
    content: str
    sequence: int
    interrupted: bool
    created_at: datetime


class ChatSessionDetail(ChatSessionRead):
    messages: list[ChatMessageRead]


class ChatUserMessageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=36)
    text: str = Field(min_length=1, max_length=1000)
    route: Literal["auto", "knowledge", "ticket"] = "auto"

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped


class ChatInterruptData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=36)
    new_input: str | None = Field(default=None, max_length=1000)
    route: Literal["auto", "knowledge", "ticket"] = "auto"

    @field_validator("new_input")
    @classmethod
    def strip_new_input(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None
