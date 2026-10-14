"""Knowledge-only support; there is deliberately no tool, memory or staff principal path."""

import logging
import re
from dataclasses import replace

from pipelines.rag import (  # type: ignore[import-untyped]
    GenerationResult,
    RagPipelineError,
    _qdrant,
    generate_answer,
    retrieve,
)

from ...core.config import Settings
from ..agents.guardrails import evidence_is_safe, normalize_untrusted, validate_input, validate_output
from ..rag.config import build_rag_config
from .schemas import SupportAnswer, SupportQuery

logger = logging.getLogger(__name__)
PUBLIC_COLLECTION = "trackflow_public"
_PUBLIC_INSTRUCTION = re.compile(
    r"\b(ignore|disregard|forget|override)\b.{0,50}\b(instructions?|rules?|polic(?:y|ies)|prompts?)\b|"
    r"\b(ignora|olvida|omite)\b.{0,50}\b(instrucciones|reglas|pol[ií]ticas)\b|"
    r"\b(revela|muestra)\b.{0,50}\b(prompt|instrucciones|credenciales|contrase[nñ]a)\b"
)
_PRIVATE = re.compile(
    r"(?i)\b(ticket|incident|tracking|track my|my (order|shipment|return)|return (label|status)|"
    r"create|cancel|approve|refund|inventory|warehouse route|internal|negotiated|"
    r"seguimiento|incidencias?|mi pedido|mi env[ií]o|mi devoluci[oó]n|reembolso|etiqueta|inventario|"
    r"crear|cancelar|aprobar|tramitar|n[uú]mero de (env[ií]o|pedido))\b|"
    r"\b(order|shipment|return)\s+(number|status)\b|"
    r"\b(issue|submit|start|process)\b.{0,40}\b(return|refund|label)\b"
)
_MESSAGES = {
    "en": {
        "contact": (
            "I can explain public policies, but cannot access private records, track shipments or submit actions. "
            "Please contact TrackFlow support."
        ),
        "clarify": "Choose United States or Spain so I can use the appropriate public policies.",
        "rejected": "I can help with TrackFlow public policies, coverage and services. I cannot follow that request.",
        "no_context": "I don't have that information in the public knowledge base. Please contact TrackFlow support.",
    },
    "es": {
        "contact": (
            "Puedo explicar políticas públicas, pero no acceder a registros privados, "
            "seguir envíos ni realizar acciones. "
            "Contacta con el equipo de TrackFlow."
        ),
        "clarify": "Selecciona Estados Unidos o España para consultar las políticas correspondientes.",
        "rejected": (
            "Puedo ayudar con políticas públicas, cobertura y servicios de TrackFlow. No puedo seguir esa solicitud."
        ),
        "no_context": (
            "No tengo esa información en la base de conocimiento pública. Contacta con el equipo de TrackFlow."
        ),
    },
}


def fallback(payload: SupportQuery, outcome: str) -> SupportAnswer:
    return SupportAnswer(answer=_MESSAGES[payload.language][outcome], outcome=outcome)  # type: ignore[arg-type]


def safe_evidence(text: str) -> bool:
    return evidence_is_safe(text) and not _PUBLIC_INSTRUCTION.search(normalize_untrusted(text))


def unsafe_input(text: str, country: str | None) -> bool:
    decision = validate_input(text, country)
    # The staff guardrail classifies even "shipment times" as tracking. Public
    # operational requests are identified separately; generic policies remain usable.
    return decision.action in {"reject", "redirect"} and not (
        decision.event and decision.event.rule_id == "shipment_source_unavailable"
    )


def answer_public_question(payload: SupportQuery, settings: Settings) -> SupportAnswer:
    if not safe_evidence(payload.question):
        return fallback(payload, "rejected")
    if unsafe_input(payload.question, payload.policy_country):
        return fallback(payload, "rejected")
    if _PRIVATE.search(normalize_untrusted(payload.question)):
        return fallback(payload, "contact")
    if payload.policy_country is None:
        return fallback(payload, "clarify")
    # Re-validate all client-supplied history, including purported assistant output.
    for item in payload.recent_context:
        if (
            unsafe_input(item.question, payload.policy_country)
            or _PRIVATE.search(normalize_untrusted(item.question))
            or not safe_evidence(item.question)
            or not safe_evidence(item.answer)
        ):
            return fallback(payload, "rejected")
    cfg = replace(
        build_rag_config(settings),
        collection=PUBLIC_COLLECTION,
        request_timeout_seconds=5.0,
        generation_timeout_seconds=15.0,
    )
    client = _qdrant(cfg.qdrant_url, cfg.qdrant_api_key, cfg.request_timeout_seconds)
    if not client.collection_exists(PUBLIC_COLLECTION):
        raise RagPipelineError("Public collection unavailable")
    # Previous questions resolve pronouns but never widen the public collection or country.
    retrieval_question = "\n".join([item.question for item in payload.recent_context] + [payload.question])
    chunks = retrieve(retrieval_question, config=cfg, jurisdiction=payload.policy_country)
    chunks = [chunk for chunk in chunks if safe_evidence(str(chunk.get("text", "")))]
    if not chunks:
        return fallback(payload, "no_context")
    answer = generate_answer(
        payload.question,
        chunks,
        cfg,
        payload.policy_country,
        answer_language=payload.language,
        recent_context=[(item.question, item.answer) for item in payload.recent_context],
    )
    if isinstance(answer, GenerationResult):
        answer = answer.answer
    if len(answer) > 4000 or validate_output(answer, payload.policy_country) is not None:
        logger.warning("public_support.query outcome=output_blocked")
        return fallback(payload, "rejected")
    return SupportAnswer(answer=answer, outcome="answered")
