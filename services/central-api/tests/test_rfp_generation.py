"""Section generation, the generator-evaluator loop, and the chained upload flow (all mocked)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pipelines.rag import RagPipelineError  # type: ignore[import-untyped]
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

OWNER = "11111111-1111-4111-8111-111111111111"

DRAFT_OK = (
    "Our warehouse offers storage capacity for your monthly orders, priced in USD. We commit to a "
    "98% on-time delivery SLA. Returns are completed in 72 hours. A volume-based discount tier table "
    "gives lower prices at higher volumes."
)
DRAFT_BAD = "Our warehouse handles storage in USD. Returns finish in 24 hours."


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
    monkeypatch.setattr(rfp_generation, "generate_answer", lambda _q, _c, _cfg: "a draft")
    ticket = RfpTicket(rfp_id="x", status="drafting", owner_user_uuid=OWNER, currency="USD")
    assert generate_section("warehouse", ticket, ["storage"], [], _rag(settings)) == "a draft"  # type: ignore[arg-type]


# --------------------------------------------------------------------------- loop


def test_generation_passes_and_advances_ticket(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket_id = _seed_drafting(engine)
    monkeypatch.setattr(rfp_generation, "generate_answer", lambda _q, _c, _cfg: DRAFT_OK)

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


def test_generation_retries_then_passes(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket_id = _seed_drafting(engine)
    drafts = iter([DRAFT_BAD, DRAFT_OK])
    monkeypatch.setattr(rfp_generation, "generate_answer", lambda _q, _c, _cfg: next(drafts))

    run_generation_for_ticket(ticket_id, _rag(settings), 2, env="test")  # type: ignore[arg-type]

    with Session(engine) as session:
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.iteration_count == 2
        assert section.evaluation_results is not None and section.evaluation_results["passed"] is True


def test_generation_stops_at_iteration_cap(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket_id = _seed_drafting(engine)
    monkeypatch.setattr(rfp_generation, "generate_answer", lambda _q, _c, _cfg: DRAFT_BAD)

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

    def boom(_q: str, _c: list[object], _cfg: object) -> str:
        raise RagPipelineError("provider down")

    monkeypatch.setattr(rfp_generation, "generate_answer", boom)
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

    def spy(_q: str, _c: list[object], _cfg: object) -> str:
        nonlocal called
        called = True
        return DRAFT_OK

    monkeypatch.setattr(rfp_generation, "generate_answer", spy)
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
    _enable_generation(app, settings)
    monkeypatch.setattr(rfp_service, "pdf_to_markdown", lambda _data: "converted markdown")
    monkeypatch.setattr(rfp_graph, "classify_document", lambda _md, _c: ClassificationResult(True, "ok"))
    monkeypatch.setattr(
        rfp_graph, "extract_metadata", lambda _md, _c: MetadataResult("Luna", "US", ["warehousing"], 5000, 20, None)
    )
    monkeypatch.setattr(rfp_graph, "extract_key_aspects", lambda dept, _md, _c: [f"{dept}-aspect"])
    monkeypatch.setattr(rfp_generation, "generate_answer", lambda _q, _c, _cfg: DRAFT_OK)

    created = client.post(
        "/rfp/tickets", files={"file": ("rfp.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth_headers
    )
    assert created.status_code == 202
    ticket_id = created.json()["id"]

    detail = client.get(f"/rfp/tickets/{ticket_id}", headers=auth_headers).json()
    assert detail["status"] == "under_evaluation"
    section = detail["sections"][0]
    assert section["evaluation_results"]["passed"] is True
