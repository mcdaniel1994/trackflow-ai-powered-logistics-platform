"""Owner-scoped chat-session lifecycle used by the Phase 4 Back Office UI."""

from dataclasses import dataclass

from sqlmodel import Session

from ...core.config import Settings
from ..agents.models import AgentConversation
from .models import ChatSession
from .repository import ChatRepository
from .schemas import ChatMessageRead, ChatSessionDetail, ChatSessionRead


@dataclass
class ChatError(Exception):
    status_code: int
    detail: str


class ChatService:
    def __init__(self, settings: Settings, session: Session) -> None:
        self.settings = settings
        self.session = session
        self.repository = ChatRepository(session)

    def _require_enabled(self) -> None:
        if not self.settings.agents_enabled:
            raise ChatError(503, "Chat is not available right now.")

    def create_session(self, *, user_id: str, jurisdiction: str | None) -> ChatSessionRead:
        self._require_enabled()
        if jurisdiction not in {"US", "ES"}:
            raise ChatError(403, "An administrator must assign your policy jurisdiction first.")
        chat_session = ChatSession(
            user_id=user_id,
            # Identity has no tenant/client claim yet. The current owner-only portfolio deployment
            # uses its authenticated user boundary as the provisional client boundary.
            client_id=user_id,
        )
        self.repository.add_session(chat_session)
        self.session.add(
            AgentConversation(
                id=chat_session.session_id,
                owner_user_uuid=user_id,
                jurisdiction=jurisdiction,
            )
        )
        self.session.commit()
        self.session.refresh(chat_session)
        return ChatSessionRead.model_validate(chat_session)

    def list_sessions(self, *, user_id: str) -> list[ChatSessionRead]:
        self._require_enabled()
        return [ChatSessionRead.model_validate(row) for row in self.repository.list_sessions_for_user(user_id)]

    def get_session(self, session_id: str, *, user_id: str) -> ChatSessionDetail:
        self._require_enabled()
        chat_session = self.repository.get_session_for_user(session_id, user_id)
        if chat_session is None:
            raise ChatError(404, "Chat session not found.")
        messages = self.repository.messages_for_user(session_id, user_id)
        return ChatSessionDetail(
            **ChatSessionRead.model_validate(chat_session).model_dump(),
            messages=[ChatMessageRead.model_validate(row) for row in messages],
        )
