"""Single-producer streaming turns shared by every socket watching one chat session."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Event, Lock
from typing import Literal
from uuid import uuid4

from pipelines.rag import GenerationCancelled  # type: ignore[import-untyped]
from sqlmodel import Session

from ...core.config import Settings
from ...db.session import get_engine
from ..agents.config import build_agent_config, is_agents_configured
from ..agents.graph import AgentRunResult, run_agent
from ..agents.memory_service import AgentMemoryError, AgentMemoryService
from ..agents.recorder import persist_run
from ..realtime.bus import RealtimeBus, chat_session_topic
from .repository import ChatRepository

logger = logging.getLogger(__name__)
ChatRoute = Literal["auto", "knowledge", "ticket"]


@dataclass(frozen=True)
class StreamingTurnContext:
    settings: Settings
    source_access_token: str
    jurisdiction: str
    evidence: list[dict[str, object]]
    user_message: dict[str, object]


@dataclass
class ActiveGeneration:
    generation_id: str
    owner_user_id: str
    cancel: Event
    task: asyncio.Task[None] | None = None
    token_parts: list[str] = field(default_factory=list)
    token_sequence: int = 0
    stream_close: Callable[[], None] | None = None
    thread_lock: Lock = field(default_factory=Lock)


def session_snapshot(session_id: str, owner_user_id: str) -> dict[str, object] | None:
    with Session(get_engine()) as session:
        repository = ChatRepository(session)
        chat_session = repository.get_session_for_user(session_id, owner_user_id)
        if chat_session is None:
            return None
        messages = repository.messages_for_user(session_id, owner_user_id)
        return {
            "session_id": chat_session.session_id,
            "status": chat_session.status,
            "messages": [
                {
                    "message_id": message.message_id,
                    "session_id": message.session_id,
                    "role": message.role,
                    "content": message.content,
                    "sequence": message.sequence,
                    "interrupted": message.interrupted,
                    "created_at": message.created_at.isoformat(),
                }
                for message in messages
            ],
        }


def _prepare_turn(
    *,
    settings: Settings,
    session_id: str,
    owner_user_id: str,
    source_access_token: str,
    question: str,
) -> StreamingTurnContext:
    if not is_agents_configured(settings):
        raise RuntimeError("agent unavailable")
    with Session(get_engine()) as session:
        repository = ChatRepository(session)
        chat_session = repository.get_session_for_user(session_id, owner_user_id)
        if chat_session is None:
            raise PermissionError("chat session unavailable")
        memory = AgentMemoryService(session)
        conversation = memory.repository.get_conversation(session_id)
        if conversation is None or conversation.owner_user_uuid != owner_user_id:
            raise PermissionError("chat conversation unavailable")
        memory.discard_pending(conversation.id)
        evidence = memory.evidence(question, conversation.jurisdiction)
        user_message = repository.append_message_for_user(
            session_id=session_id,
            user_id=owner_user_id,
            role="user",
            content=question,
        )
        chat_session.status = "active"
        session.add(chat_session)
        session.commit()
        if user_message is None:
            raise RuntimeError("chat message unavailable")
        session.refresh(user_message)
        return StreamingTurnContext(
            settings,
            source_access_token,
            conversation.jurisdiction,
            evidence,
            {
                "message_id": user_message.message_id,
                "session_id": user_message.session_id,
                "role": user_message.role,
                "content": user_message.content,
                "sequence": user_message.sequence,
                "interrupted": user_message.interrupted,
                "created_at": user_message.created_at.isoformat(),
            },
        )


# Matches the agents service preview cap (telemetry standard §8): truncated, content-limited previews.
_SUMMARY_MAX_CHARS = 200


def _complete_turn(
    *,
    session_id: str,
    owner_user_id: str,
    question: str,
    result: AgentRunResult,
    env: str,
    settings: Settings,
) -> str:
    with Session(get_engine()) as session:
        repository = ChatRepository(session)
        chat_session = repository.get_session_for_user(session_id, owner_user_id)
        if chat_session is None or not result.answer:
            raise RuntimeError("chat completion unavailable")
        memory = AgentMemoryService(session)
        conversation = memory.repository.get_conversation(session_id)
        if conversation is not None and result.status == "ok":
            try:
                _proposal, rejection_reason = memory.create_proposal(
                    conversation=conversation,
                    raw_candidate=result.memory_candidate,
                    trace_id=result.trace_id,
                    question=question,
                )
                if rejection_reason:
                    result.guardrail_events.append(
                        {
                            "layer": "memory",
                            "rule_id": rejection_reason,
                            "category": "content",
                            "outcome": "blocked",
                            "duration_ms": 0,
                        }
                    )
            except AgentMemoryError:
                logger.warning("chat_memory_candidate_failed error_type=AgentMemoryError")
        message = repository.append_message_for_user(
            session_id=session_id,
            user_id=owner_user_id,
            role="assistant",
            content=result.answer,
        )
        if message is None:
            raise RuntimeError("chat completion unavailable")
        chat_session.status = "active"
        session.add(chat_session)
        session.commit()
        session.refresh(message)
    # Store truncated previews only when content capture is enabled and no guardrail fired
    # (telemetry standard §8). Mirrors the /agent/query path in domains/agents/service.py; chat
    # content is already persisted in chat_messages under the approved Engagement 10 exception.
    store = settings.agents_store_content and not result.guardrail_events
    input_summary = question[:_SUMMARY_MAX_CHARS] if store else None
    output_summary = result.answer[:_SUMMARY_MAX_CHARS] if (store and result.answer) else None
    persist_run(result, env=env, input_summary=input_summary, output_summary=output_summary)
    return message.message_id


def _persist_interrupted(session_id: str, owner_user_id: str, partial: str) -> str | None:
    with Session(get_engine()) as session:
        repository = ChatRepository(session)
        chat_session = repository.get_session_for_user(session_id, owner_user_id)
        if chat_session is None:
            return None
        message_id: str | None = None
        if partial.strip():
            message = repository.append_message_for_user(
                session_id=session_id,
                user_id=owner_user_id,
                role="assistant",
                content=partial,
                interrupted=True,
            )
            message_id = message.message_id if message is not None else None
        chat_session.status = "interrupted"
        session.add(chat_session)
        session.commit()
        return message_id


class ChatGenerationManager:
    """Own at most one model call per session and fan its events to all subscribers."""

    def __init__(self, bus: RealtimeBus) -> None:
        self.bus = bus
        self._active: dict[str, ActiveGeneration] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        settings: Settings,
        session_id: str,
        owner_user_id: str,
        source_access_token: str,
        question: str,
        route: ChatRoute,
    ) -> bool:
        async with self._lock:
            if session_id in self._active:
                return False
            active = ActiveGeneration(uuid4().hex, owner_user_id, Event())
            self._active[session_id] = active
            active.task = asyncio.create_task(
                self._run(
                    active=active,
                    settings=settings,
                    session_id=session_id,
                    source_access_token=source_access_token,
                    question=question,
                    route=route,
                )
            )
            return True

    async def interrupt(
        self,
        *,
        settings: Settings,
        session_id: str,
        owner_user_id: str,
        source_access_token: str,
        new_input: str | None,
        route: ChatRoute,
    ) -> bool:
        async with self._lock:
            active = self._active.get(session_id)
            if active is None or active.owner_user_id != owner_user_id:
                return False
            active.cancel.set()
            task = active.task
            with active.thread_lock:
                stream_close = active.stream_close
        if stream_close is not None:
            await asyncio.to_thread(stream_close)
        if task is not None:
            await task
        if new_input:
            return await self.start(
                settings=settings,
                session_id=session_id,
                owner_user_id=owner_user_id,
                source_access_token=source_access_token,
                question=new_input,
                route=route,
            )
        return True

    async def active_snapshot(self, session_id: str, owner_user_id: str) -> dict[str, object] | None:
        """Return a consistent owner-checked partial generation for reconnect recovery."""
        async with self._lock:
            active = self._active.get(session_id)
            if active is None or active.owner_user_id != owner_user_id:
                return None
            with active.thread_lock:
                return {
                    "generation_id": active.generation_id,
                    "content": "".join(active.token_parts),
                    "sequence": active.token_sequence,
                }

    async def _run(
        self,
        *,
        active: ActiveGeneration,
        settings: Settings,
        session_id: str,
        source_access_token: str,
        question: str,
        route: ChatRoute,
    ) -> None:
        topic = chat_session_topic(session_id)
        def publish_token(delta: str) -> None:
            if active.cancel.is_set():
                raise GenerationCancelled("generation cancelled")
            with active.thread_lock:
                active.token_parts.append(delta)
                active.token_sequence += 1
                sequence = active.token_sequence
            self.bus.publish(
                topic,
                "token_chunk",
                {
                    "session_id": session_id,
                    "generation_id": active.generation_id,
                    "token": delta,
                    "sequence": sequence,
                },
            )

        def register_stream_close(close: Callable[[], None]) -> None:
            close_immediately = False
            with active.thread_lock:
                if active.cancel.is_set():
                    close_immediately = True
                else:
                    active.stream_close = close
            if close_immediately:
                close()

        try:
            context = await asyncio.to_thread(
                _prepare_turn,
                settings=settings,
                session_id=session_id,
                owner_user_id=active.owner_user_id,
                source_access_token=source_access_token,
                question=question,
            )
            self.bus.publish(
                topic,
                "user_message",
                {
                    "session_id": session_id,
                    "generation_id": active.generation_id,
                    "message": context.user_message,
                },
            )
            config = build_agent_config(context.settings, context.source_access_token)
            result = await asyncio.to_thread(
                run_agent,
                question,
                config,
                context.jurisdiction,
                context.evidence,
                route_preference=route,
                token_callback=publish_token,
                cancelled=active.cancel.is_set,
                stream_started=register_stream_close,
            )
            if active.cancel.is_set():
                raise GenerationCancelled("generation cancelled")
            message_id = await asyncio.to_thread(
                _complete_turn,
                session_id=session_id,
                owner_user_id=active.owner_user_id,
                question=question,
                result=result,
                env=settings.app_env,
                settings=settings,
            )
            self.bus.publish(
                topic,
                "generation_completed",
                {
                    "session_id": session_id,
                    "generation_id": active.generation_id,
                    "message_id": message_id,
                    "route_taken": result.route_taken,
                },
            )
        except GenerationCancelled:
            with active.thread_lock:
                partial = "".join(active.token_parts)
            interrupted_message_id = await asyncio.to_thread(
                _persist_interrupted,
                session_id,
                active.owner_user_id,
                partial,
            )
            self.bus.publish(
                topic,
                "generation_interrupted",
                {
                    "session_id": session_id,
                    "generation_id": active.generation_id,
                    "message_id": interrupted_message_id,
                    "status": "interrupted",
                },
            )
        except Exception as exc:
            logger.warning("chat_generation_failed error_type=%s", type(exc).__name__)
            self.bus.publish(
                topic,
                "generation_failed",
                {
                    "session_id": session_id,
                    "generation_id": active.generation_id,
                    "detail": "The assistant is temporarily unavailable.",
                },
            )
        finally:
            async with self._lock:
                if self._active.get(session_id) is active:
                    self._active.pop(session_id, None)

    async def close(self) -> None:
        async with self._lock:
            active = tuple(self._active.values())
            for generation in active:
                generation.cancel.set()
            tasks = tuple(generation.task for generation in active if generation.task is not None)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
