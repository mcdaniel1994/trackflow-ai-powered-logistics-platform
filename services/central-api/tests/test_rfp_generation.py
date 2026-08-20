"""Section generation, the generator-evaluator loop, and the chained upload flow (all mocked)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pipelines.rag import GenerationResult, RagPipelineError  # type: ignore[import-untyped]
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.core.config import Settings, get_settings
from central_api.domains.agents.models import AgentRun
from central_api.domains.rag.config import build_rag_config
from central_api.domains.rfp import generation as rfp_generation
from central_api.domains.rfp import graph as rfp_graph
from central_api.domains.rfp import service as rfp_service
from central_api.domains.rfp.agents import ClassificationResult, MetadataResult
from central_api.domains.rfp.generation import generate_section, run_generation_for_ticket
from central_api.domains.rfp.models import RfpDepartmentSection, RfpTicket
from central_api.domains.rfp.processor import process_rfp_ticket

OWNER = "11111111-1111-4111-8111-111111111111"

DRAFT_OK = (
    "Our warehouse offers storage capacity for your monthly orders, priced in USD. We commit to a "
    "98% on-time delivery SLA. Returns are completed in 72 hours. A volume-based discount tier table "
    "gives lower prices at higher volumes."
)
DRAFT_BAD = "Our warehouse handles storage in USD. Returns finish in 24 hours."

# The DeepSeek drafting model (deepseek-chat) is unpriced, so these counters yield tokens with cost=None.
_COUNTERS = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


def _result(answer: str, counters: dict[str, int] | None = _COUNTERS) -> GenerationResult:
    return GenerationResult(answer, None, counters)


@pytest.fixture(autouse=True)
def _no_live_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Grounding calls retrieve(); stub it so unit tests never reach a live Qdrant."""
    monkeypatch.setattr(rfp_generation, "retrieve", lambda *_a, **_k: [])


def _seed_drafting(engine: Engine) -> str:
    with Session(engine) as session:
        ticket = RfpTicket(
            rfp_id="RFP-GEN",
            status="drafting",
            owner_user_uuid=OWNER,
            client_country="US",
            currency="USD",
            monthly_volume=5000,
            departments_needed=["warehouse"],
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        session.add(
            RfpDepartmentSection(
                ticket_id=ticket.id,
                department_id="warehouse",
                approval_status="pending",
                key_aspects={"aspects": ["storage capacity"]},
            )
        )
        session.commit()
        return ticket.id


def _rag(settings: Settings) -> object:
    return build_rag_config(settings)


# --------------------------------------------------------------------------- generator


def test_generate_section_uses_generator(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr(rfp_generation, "complete_with_usage", lambda _sys, _user, _cfg: _result("a draft"))
    ticket = RfpTicket(rfp_id="x", status="drafting", owner_user_uuid=OWNER, currency="USD")
    draft, usage = generate_section("warehouse", ticket, ["storage"], [], _rag(settings))  # type: ignore[arg-type]
    assert draft == "a draft"
    assert usage is not None and usage.total_tokens == 150
    assert usage.cost_usd is None  # deepseek-chat is unpriced


# --------------------------------------------------------------------------- loop


def test_generation_passes_and_advances_ticket(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket_id = _seed_drafting(engine)
    monkeypatch.setattr(rfp_generation, "complete_with_usage", lambda _sys, _user, _cfg: _result(DRAFT_OK))

    run_generation_for_ticket(ticket_id, _rag(settings), 2, env="test")  # type: ignore[arg-type]

    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None and ticket.status == "under_evaluation"
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.draft_content == DRAFT_OK
        assert section.evaluation_results is not None and section.evaluation_results["passed"] is True
        assert section.iteration_count == 1
        runs = session.exec(select(AgentRun).where(AgentRun.agent_name == "trackflow-rfp-generation")).all()
        assert len(runs) == 1 and runs[0].route_taken == "generate"
        # The generation step captured the drafting model's tokens (cost None: deepseek-chat unpriced).
        assert runs[0].total_tokens == 150 and runs[0].total_cost_usd is None


def test_generation_retries_then_passes(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket_id = _seed_drafting(engine)
    drafts = iter([DRAFT_BAD, DRAFT_OK])
    monkeypatch.setattr(rfp_generation, "complete_with_usage", lambda _sys, _user, _cfg: _result(next(drafts)))

    run_generation_for_ticket(ticket_id, _rag(settings), 2, env="test")  # type: ignore[arg-type]

    with Session(engine) as session:
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.iteration_count == 2
        assert section.evaluation_results is not None and section.evaluation_results["passed"] is True
        runs = session.exec(select(AgentRun).where(AgentRun.agent_name == "trackflow-rfp-generation")).all()
        # Two drafting calls in the loop: tokens sum across iterations, cost stays None (unpriced).
        assert runs[0].total_tokens == 300 and runs[0].total_cost_usd is None


def test_generation_stops_at_iteration_cap(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket_id = _seed_drafting(engine)
    monkeypatch.setattr(rfp_generation, "complete_with_usage", lambda _sys, _user, _cfg: _result(DRAFT_BAD))

    run_generation_for_ticket(ticket_id, _rag(settings), 2, env="test")  # type: ignore[arg-type]

    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None and ticket.status == "under_evaluation"
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.iteration_count == 2  # capped, not looping forever
        assert section.evaluation_results is not None and section.evaluation_results["passed"] is False


def test_generation_handles_provider_error(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket_id = _seed_drafting(engine)

    def boom(_sys: str, _user: str, _cfg: object) -> GenerationResult:
        raise RagPipelineError("provider down")

    monkeypatch.setattr(rfp_generation, "complete_with_usage", boom)
    run_generation_for_ticket(ticket_id, _rag(settings), 2, env="test")  # type: ignore[arg-type]

    with Session(engine) as session:
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.draft_content is None
        assert section.evaluation_results == {"error": True}


def test_generation_skips_non_drafting_ticket(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(engine) as session:
        ticket = RfpTicket(rfp_id="RFP-ANALYZING", status="analyzing", owner_user_uuid=OWNER)
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        ticket_id = ticket.id
    called = False

    def spy(_sys: str, _user: str, _cfg: object) -> GenerationResult:
        nonlocal called
        called = True
        return _result(DRAFT_OK)

    monkeypatch.setattr(rfp_generation, "complete_with_usage", spy)
    run_generation_for_ticket(ticket_id, _rag(settings), 2, env="test")  # type: ignore[arg-type]
    assert called is False  # idempotency guard: only drafting tickets are generated


# --------------------------------------------------------------------------- chained upload flow


def _enable_generation(app: FastAPI, base: Settings) -> Settings:
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        rfp_enabled=True,
        openai_api_key="test-openai",
        deepseek_api_key="test-deepseek",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    return configured


def test_upload_chains_into_generation(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _enable_generation(app, settings)
    monkeypatch.setattr(rfp_service, "pdf_to_markdown", lambda _data: "converted markdown")
    monkeypatch.setattr(rfp_graph, "classify_document", lambda _md, _c: (ClassificationResult(True, "ok"), None))
    monkeypatch.setattr(
        rfp_graph,
        "extract_metadata",
        lambda _md, _c: (MetadataResult("Luna", "US", ["warehousing"], 5000, 20, None), None),
    )
    monkeypatch.setattr(rfp_graph, "extract_key_aspects", lambda dept, _md, _c: ([f"{dept}-aspect"], None))
    monkeypatch.setattr(rfp_generation, "complete_with_usage", lambda _sys, _user, _cfg: _result(DRAFT_OK))
    queued: list[str] = []
    monkeypatch.setattr(rfp_service, "enqueue_rfp_processing", queued.append)

    created = client.post(
        "/rfp/tickets", files={"file": ("rfp.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth_headers
    )
    assert created.status_code == 202
    ticket_id = created.json()["id"]
    assert queued == [ticket_id]

    assert process_rfp_ticket(ticket_id, configured) == "waiting_for_approval"
    detail = client.get(f"/rfp/tickets/{ticket_id}", headers=auth_headers).json()
    assert detail["status"] == "waiting_for_approval"
    section = detail["sections"][0]
    assert section["evaluation_results"]["passed"] is True
