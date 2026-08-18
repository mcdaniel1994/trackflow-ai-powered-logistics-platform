"""Phase 3 chat-history ownership, ordering, constraints, and retention."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from central_api.domains.chat.models import ChatMessage, ChatSession
from central_api.domains.chat.repository import ChatRepository
from scripts import prune_chat_history

FIRST_OWNER = "11111111-1111-4111-8111-111111111111"
SECOND_OWNER = "22222222-2222-4222-8222-222222222222"
FIRST_CLIENT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SECOND_CLIENT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _session(*, user_id: str = FIRST_OWNER, client_id: str = FIRST_CLIENT, **updates: object) -> ChatSession:
    return ChatSession(user_id=user_id, client_id=client_id, **updates)


def test_schema_has_exact_chat_entities_and_ordering_indexes(engine: Engine) -> None:
    inspector = inspect(engine)
    assert {column["name"] for column in inspector.get_columns("chat_sessions")} == {
        "session_id",
        "agent_id",
        "user_id",
        "client_id",
        "status",
        "created_at",
        "updated_at",
    }
    assert {column["name"] for column in inspector.get_columns("chat_messages")} == {
        "message_id",
        "session_id",
        "role",
        "content",
        "sequence",
        "interrupted",
        "created_at",
    }
    assert "ix_chat_sessions_user_updated" in {
        index["name"] for index in inspector.get_indexes("chat_sessions")
    }
    message_indexes = {index["name"]: index for index in inspector.get_indexes("chat_messages")}
    assert message_indexes["uq_chat_messages_session_sequence"]["unique"] is True


def test_repository_reads_sessions_and_messages_only_for_owner(engine: Engine) -> None:
    with Session(engine) as session:
        repository = ChatRepository(session)
        first = _session()
        second = _session(user_id=SECOND_OWNER, client_id=SECOND_CLIENT)
        repository.add_session(first)
        repository.add_session(second)
        session.commit()

        first_message = repository.append_message_for_user(
            session_id=first.session_id,
            user_id=FIRST_OWNER,
            role="user",
            content="Where is my parcel?",
        )
        second_message = repository.append_message_for_user(
            session_id=second.session_id,
            user_id=SECOND_OWNER,
            role="assistant",
            content="I can help with that.",
        )
        session.commit()

        assert first_message is not None and first_message.sequence == 1
        assert second_message is not None and second_message.sequence == 1
        assert [row.session_id for row in repository.list_sessions_for_user(FIRST_OWNER)] == [first.session_id]
        assert repository.get_session_for_user(first.session_id, SECOND_OWNER) is None
        assert repository.messages_for_user(first.session_id, SECOND_OWNER) == []
        assert [row.content for row in repository.messages_for_user(first.session_id, FIRST_OWNER)] == [
            "Where is my parcel?"
        ]
        assert (
            repository.append_message_for_user(
                session_id=first.session_id,
                user_id=SECOND_OWNER,
                role="user",
                content="Cross-owner write",
            )
            is None
        )


def test_append_allocates_unique_sequence_under_concurrency(engine: Engine) -> None:
    with Session(engine) as session:
        chat_session = _session()
        session.add(chat_session)
        session.commit()
        session_id = chat_session.session_id

    barrier = Barrier(2)

    def append(index: int) -> int:
        with Session(engine) as session:
            barrier.wait()
            message = ChatRepository(session).append_message_for_user(
                session_id=session_id,
                user_id=FIRST_OWNER,
                role="user" if index == 1 else "assistant",
                content=f"message {index}",
            )
            assert message is not None
            session.commit()
            return message.sequence

    with ThreadPoolExecutor(max_workers=2) as executor:
        sequences = sorted(executor.map(append, (1, 2)))

    assert sequences == [1, 2]
    with Session(engine) as session:
        messages = ChatRepository(session).messages_for_user(session_id, FIRST_OWNER)
        assert [message.sequence for message in messages] == [1, 2]


@pytest.mark.parametrize(
    "message",
    [
        ChatMessage(session_id="placeholder", role="system", content="invalid role", sequence=1),
        ChatMessage(session_id="placeholder", role="user", content="", sequence=1),
        ChatMessage(session_id="placeholder", role="user", content="invalid sequence", sequence=0),
        ChatMessage(
            session_id="placeholder",
            role="user",
            content="users cannot be interrupted",
            sequence=1,
            interrupted=True,
        ),
    ],
)
def test_database_rejects_invalid_chat_messages(engine: Engine, message: ChatMessage) -> None:
    with Session(engine) as session:
        chat_session = _session()
        session.add(chat_session)
        session.commit()
        message.session_id = chat_session.session_id
        session.add(message)
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "updates",
    [
        {"agent_id": "other_agent"},
        {"status": "unknown"},
    ],
)
def test_database_rejects_invalid_chat_sessions(engine: Engine, updates: dict[str, object]) -> None:
    with Session(engine) as session:
        session.add(_session(**updates))
        with pytest.raises(IntegrityError):
            session.commit()


def test_ninety_day_retention_is_bounded_and_cascades_messages(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    with Session(engine) as session:
        expired = _session(updated_at=now - timedelta(days=91))
        retained = _session(updated_at=now - timedelta(days=89))
        session.add(expired)
        session.add(retained)
        session.flush()
        session.add(
            ChatMessage(
                session_id=expired.session_id,
                role="assistant",
                content="expired content",
                sequence=1,
            )
        )
        session.add(
            ChatMessage(
                session_id=retained.session_id,
                role="assistant",
                content="retained content",
                sequence=1,
            )
        )
        session.commit()
        retained_id = retained.session_id

    monkeypatch.setattr(prune_chat_history, "get_engine", lambda: engine)
    assert prune_chat_history.prune_once(now=now, batch_size=1) == 1

    with Session(engine) as session:
        sessions = session.exec(select(ChatSession)).all()
        messages = session.exec(select(ChatMessage)).all()
        assert [row.session_id for row in sessions] == [retained_id]
        assert [row.content for row in messages] == ["retained content"]


@pytest.mark.parametrize("limit", [0, 5_001])
def test_retention_batch_size_is_bounded(limit: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 5000"):
        prune_chat_history.prune_once(batch_size=limit)
