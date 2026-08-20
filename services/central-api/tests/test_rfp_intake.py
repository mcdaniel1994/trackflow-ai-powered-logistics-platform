"""Intake graph, background runner, and upload endpoint (all provider/PDF calls mocked)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.core.config import Settings, get_settings
from central_api.domains.agents.models import AgentRun
from central_api.domains.agents.pricing import ModelUsage
from central_api.domains.rfp import graph as rfp_graph
from central_api.domains.rfp import intake as rfp_intake
from central_api.domains.rfp import service as rfp_service
from central_api.domains.rfp.agents import ClassificationResult, MetadataResult, RfpAgentError
from central_api.domains.rfp.config import RfpConfig
from central_api.domains.rfp.graph import IntakeOutcome, run_intake
from central_api.domains.rfp.models import RfpTicket

CFG = RfpConfig(model="m", timeout_seconds=1.0, openai_api_key="k")
OWNER = "11111111-1111-4111-8111-111111111111"


def _patch_graph_agents(
    monkeypatch: pytest.MonkeyPatch,
    *,
    is_rfp: bool = True,
    reason: str = "ok",
    services: list[str] | None = None,
    usage: ModelUsage | None = None,
) -> None:
    # The intake agents now return (result, usage); the graph nodes unpack the usage onto the trace.
    services = ["warehousing", "lastmile"] if services is None else services
    monkeypatch.setattr(
        rfp_graph, "classify_document", lambda _md, _c: (ClassificationResult(is_rfp, reason), usage)
    )
    monkeypatch.setattr(
        rfp_graph,
        "extract_metadata",
        lambda _md, _c: (MetadataResult("Luna", "US", services, 5000, 20, None), usage),
    )
    monkeypatch.setattr(rfp_graph, "extract_key_aspects", lambda dept, _md, _c: ([f"{dept}-aspect"], usage))


# --------------------------------------------------------------------------- graph


def test_run_intake_routes_valid_rfp(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_graph_agents(monkeypatch)
    outcome = run_intake("doc", CFG)
    assert outcome.status == "routed"
    assert outcome.departments == ["warehouse", "lastmile"]
    assert outcome.metadata is not None and outcome.metadata["currency"] == "USD"
    assert [step["node_name"] for step in outcome.steps] == [
        "classify",
        "extract_metadata",
        "orchestrate",
        "workers",
        "synthesize",
    ]
    assert [step["sequence"] for step in outcome.steps] == [1, 2, 3, 4, 5]


def test_run_intake_discards_non_rfp(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_graph_agents(monkeypatch, is_rfp=False, reason="vendor pitch")
    outcome = run_intake("doc", CFG)
    assert outcome.status == "discarded"
    assert outcome.discard_reason == "vendor pitch"
    assert [step["node_name"] for step in outcome.steps] == ["classify"]  # flow stopped early


def test_run_intake_reports_agent_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_md: str, _c: RfpConfig) -> ClassificationResult:
        raise RfpAgentError("model down")

    monkeypatch.setattr(rfp_graph, "classify_document", boom)
    outcome = run_intake("doc", CFG)
    assert outcome.status == "error" and outcome.error == "model down"


# --------------------------------------------------------------------------- background runner


def _seed_ticket(engine: Engine, *, status: str = "analyzing", markdown: str = "doc") -> str:
    with Session(engine) as session:
        ticket = RfpTicket(rfp_id="RFP-RUN", status=status, owner_user_uuid=OWNER, markdown_text=markdown)
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return ticket.id


def _outcome(status: str) -> IntakeOutcome:
    now = datetime.now(UTC).isoformat()
    step = {
        "node_name": "classify",
        "status": "ok",
        "started_at": now,
        "ended_at": now,
        "duration_ms": 1,
        "tokens": None,
        "cost_usd": None,
        "notes": None,
        "sequence": 1,
    }
    return IntakeOutcome(
        status=status,
        is_rfp=status != "discarded",
        discard_reason="vendor pitch" if status == "discarded" else None,
        metadata={
            "client_name": "Luna",
            "client_country": "US",
            "currency": "USD",
            "services_requested": ["warehousing"],
            "monthly_volume": 5000,
            "deadline_days": 20,
            "budget_range": None,
        },
        departments=["warehouse"],
        department_aspects={"warehouse": ["capacity"]},
        routing_summary={"departments": [{"department_id": "warehouse", "ask": ["capacity"]}]},
        error=None,
        steps=[step],
    )


def test_runner_routes_ticket_and_records_trace(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = _seed_ticket(engine)
    monkeypatch.setattr(rfp_intake, "run_intake", lambda _md, _c: _outcome("routed"))

    rfp_intake.run_intake_for_ticket(ticket_id, CFG, env="test")

    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None
        assert ticket.status == "drafting"
        assert ticket.client_country == "US" and ticket.currency == "USD"
        assert ticket.departments_needed == ["warehouse"]
        runs = session.exec(select(AgentRun).where(AgentRun.agent_name == "trackflow-rfp-intake")).all()
        assert len(runs) == 1 and runs[0].route_taken == "routed"
        assert runs[0].input_summary is None  # content-free trace


def test_runner_discards_non_rfp(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = _seed_ticket(engine)
    monkeypatch.setattr(rfp_intake, "run_intake", lambda _md, _c: _outcome("discarded"))

    rfp_intake.run_intake_for_ticket(ticket_id, CFG, env="test")

    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None
        assert ticket.status == "discarded" and ticket.discard_reason == "vendor pitch"


def test_runner_error_leaves_ticket_analyzing(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_id = _seed_ticket(engine)
    monkeypatch.setattr(rfp_intake, "run_intake", lambda _md, _c: _outcome("error"))

    rfp_intake.run_intake_for_ticket(ticket_id, CFG, env="test")

    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None and ticket.status == "analyzing"  # reprocessable, not discarded


def test_runner_missing_ticket_is_noop(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rfp_intake, "run_intake", lambda _md, _c: _outcome("routed"))
    rfp_intake.run_intake_for_ticket("does-not-exist", CFG, env="test")  # must not raise


def test_runner_records_token_usage_from_agents(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    # Real intake graph with agents returning priced usage: the persisted run carries non-null tokens.
    ticket_id = _seed_ticket(engine)
    usage = ModelUsage(input_tokens=10, output_tokens=5, total_tokens=15, cost_usd=0.001)
    _patch_graph_agents(monkeypatch, usage=usage)

    rfp_intake.run_intake_for_ticket(ticket_id, CFG, env="test")

    with Session(engine) as session:
        runs = session.exec(select(AgentRun).where(AgentRun.agent_name == "trackflow-rfp-intake")).all()
        assert len(runs) == 1
        assert runs[0].total_tokens is not None and runs[0].total_tokens > 0
        assert runs[0].total_cost_usd is not None  # the stubbed usage carries a priced cost
        assert runs[0].input_summary is None  # intake stays content-free


# --------------------------------------------------------------------------- upload endpoint


def _enable_intake(app: FastAPI, base: Settings) -> Settings:
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        rfp_enabled=True,
        openai_api_key="test-openai",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    return configured


def test_upload_requires_authentication(client: TestClient) -> None:
    response = client.post("/rfp/tickets", files={"file": ("rfp.pdf", b"%PDF-1.4", "application/pdf")})
    assert response.status_code == 401


def test_upload_unavailable_when_intake_not_configured(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
) -> None:
    # Feature flag on but no OpenAI key -> intake is not configured. Force the key empty explicitly:
    # init kwargs override any OPENAI_API_KEY present in a local .env (absent in CI).
    configured = Settings(
        database_url=settings.database_url,
        identity_jwt_public_key=settings.identity_jwt_public_key,
        rfp_enabled=True,
        openai_api_key="",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    response = client.post(
        "/rfp/tickets", files={"file": ("rfp.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth_headers
    )
    assert response.status_code == 503


def test_upload_rejects_non_pdf(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
) -> None:
    _enable_intake(app, settings)
    response = client.post(
        "/rfp/tickets", files={"file": ("notes.txt", b"hello", "text/plain")}, headers=auth_headers
    )
    assert response.status_code == 415


def test_upload_creates_ticket_then_background_intake_routes(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_intake(app, settings)
    monkeypatch.setattr(rfp_service, "pdf_to_markdown", lambda _data: "converted markdown")
    _patch_graph_agents(monkeypatch)

    created = client.post(
        "/rfp/tickets", files={"file": ("rfp.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth_headers
    )
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "analyzing"
    ticket_id = body["id"]

    # TestClient runs background tasks after the response, so intake has completed by the next read.
    detail = client.get(f"/rfp/tickets/{ticket_id}", headers=auth_headers).json()
    assert detail["status"] == "drafting"
    assert detail["client_country"] == "US" and detail["currency"] == "USD"
    assert [section["department_id"] for section in detail["sections"]] == ["lastmile", "warehouse"]


def test_upload_translates_conversion_failure(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_intake(app, settings)

    def boom(_data: bytes) -> str:
        from central_api.domains.rfp.document import DocumentError

        raise DocumentError("No readable text was found in the PDF.")

    monkeypatch.setattr(rfp_service, "pdf_to_markdown", boom)
    response = client.post(
        "/rfp/tickets", files={"file": ("rfp.pdf", b"%PDF-1.4", "application/pdf")}, headers=auth_headers
    )
    assert response.status_code == 400
