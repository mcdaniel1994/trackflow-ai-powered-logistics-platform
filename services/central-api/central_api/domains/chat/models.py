"""SQLModel persistence for owner-scoped chat history."""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel

CHAT_AGENT_ID = "first_line_cx"
CHAT_SESSION_STATUSES: tuple[str, ...] = ("active", "interrupted", "closed")
CHAT_MESSAGE_ROLES: tuple[str, ...] = ("user", "assistant")


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChatSession(SQLModel, table=True):
    """One owner-bound conversation; ``session_id`` is also the LangGraph thread id."""

    __tablename__ = "chat_sessions"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("agent_id = 'first_line_cx'", name="ck_chat_sessions_agent"),
        CheckConstraint(
            "status IN ('active', 'interrupted', 'closed')",
            name="ck_chat_sessions_status",
        ),
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
        Index("ix_chat_sessions_client_updated", "client_id", "updated_at"),
    )

    session_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    agent_id: str = Field(default=CHAT_AGENT_ID, sa_column=Column(String(32), nullable=False))
    user_id: str = Field(sa_column=Column(String(36), nullable=False))
    client_id: str = Field(sa_column=Column(String(36), nullable=False))
    status: str = Field(default="active", sa_column=Column(String(16), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ChatMessage(SQLModel, table=True):
    """One ordered user-visible chat message; partial assistant text may be interrupted."""

    __tablename__ = "chat_messages"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
        CheckConstraint("sequence >= 1", name="ck_chat_messages_sequence"),
        CheckConstraint("char_length(content) > 0", name="ck_chat_messages_content"),
        CheckConstraint(
            "interrupted = false OR role = 'assistant'",
            name="ck_chat_messages_interrupted_role",
        ),
        Index("uq_chat_messages_session_sequence", "session_id", "sequence", unique=True),
    )

    message_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    session_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    role: str = Field(sa_column=Column(String(16), nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    sequence: int = Field(sa_column=Column(Integer, nullable=False))
    interrupted: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
