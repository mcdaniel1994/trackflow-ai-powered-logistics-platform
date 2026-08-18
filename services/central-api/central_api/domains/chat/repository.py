"""Owner-scoped and bounded persistence access for chat history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from .models import ChatMessage, ChatSession, utc_now


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_session(self, chat_session: ChatSession) -> None:
        self.session.add(chat_session)

    def get_session_for_user(self, session_id: str, user_id: str) -> ChatSession | None:
        return self.session.exec(
            select(ChatSession).where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == user_id,
            )
        ).one_or_none()

    def list_sessions_for_user(self, user_id: str, *, limit: int = 50) -> list[ChatSession]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        return list(
            self.session.exec(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc(), ChatSession.session_id)  # type: ignore[attr-defined]
                .limit(limit)
            ).all()
        )

    def messages_for_user(
        self,
        session_id: str,
        user_id: str,
        *,
        limit: int = 1_000,
    ) -> list[ChatMessage]:
        if limit < 1 or limit > 1_000:
            raise ValueError("limit must be between 1 and 1000")
        return list(
            self.session.exec(
                select(ChatMessage)
                .join(
                    ChatSession,
                    col(ChatSession.session_id) == col(ChatMessage.session_id),
                )
                .where(
                    ChatMessage.session_id == session_id,
                    ChatSession.user_id == user_id,
                )
                .order_by(ChatMessage.sequence)  # type: ignore[arg-type]
                .limit(limit)
            ).all()
        )

    def append_message_for_user(
        self,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        interrupted: bool = False,
    ) -> ChatMessage | None:
        """Lock the owner-scoped session so sequence allocation is atomic per conversation."""
        chat_session = self.session.exec(
            select(ChatSession)
            .where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == user_id,
            )
            .with_for_update()
        ).one_or_none()
        if chat_session is None:
            return None
        next_sequence = int(
            self.session.exec(
                select(func.coalesce(func.max(ChatMessage.sequence), 0)).where(
                    ChatMessage.session_id == session_id
                )
            ).one()
        ) + 1
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sequence=next_sequence,
            interrupted=interrupted,
        )
        chat_session.updated_at = utc_now()
        self.session.add(chat_session)
        self.session.add(message)
        self.session.flush()
        return message

    def delete_expired_sessions(self, cutoff: datetime, *, limit: int = 500) -> int:
        """Delete one oldest-first batch; messages cascade from their session."""
        if limit < 1 or limit > 5_000:
            raise ValueError("limit must be between 1 and 5000")
        expired_ids = list(
            self.session.exec(
                select(ChatSession.session_id)
                .where(ChatSession.updated_at < cutoff)
                .order_by(ChatSession.updated_at, ChatSession.session_id)  # type: ignore[arg-type]
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        if not expired_ids:
            return 0
        result = self.session.execute(
            delete(ChatSession).where(col(ChatSession.session_id).in_(expired_ids))
        )
        return int(cast(Any, result).rowcount or 0)
