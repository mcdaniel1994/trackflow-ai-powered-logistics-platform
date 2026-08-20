"""Human approval, interrupt/resume, arbitration, and final-document completion (Phase 3).

Exercises the real LangGraph ``interrupt()`` + durable Postgres checkpointer against the disposable
database. The only mock is the redraft generator on the ``request_changes`` path.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.core.config import Settings, get_settings
from central_api.domains.agents.models import AgentNodeStep, AgentRun
from central_api.domains.rag.config import build_rag_config
from central_api.domains.rfp import approval as rfp_approval
from central_api.domains.rfp.approval import start_ticket_approval
from central_api.domains.rfp.models import RfpDepartmentSection, RfpFinalDocument, RfpTicket
from central_api.domains.rfp.service import RfpError, RfpService

OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"

COMPLIANT = (
    "Our warehouse offers storage capacity priced in USD with a 98% on-time delivery SLA. Returns "
    "complete in 72 hours. A volume-based discount tier table lowers prices at higher volumes."
)


def _configured(settings: Settings) -> Settings:
    return Settings(
        database_url=settings.database_url,
        rfp_enabled=True,
        openai_api_key="test-openai",
        deepseek_api_key="test-deepseek",
    )


def _seed_under_eval(engine: Engine, *, departments: list[str], owner: str = OWNER, iteration: int = 1) -> str:
    with Session(engine) as session:
        ticket = RfpTicket(
            rfp_id=f"RFP-{departments[0]}-{owner[:4]}-{iteration}",
            status="under_evaluation",
            owner_user_uuid=owner,
            client_country="US",
            currency="USD",
            monthly_volume=5000,
            departments_needed=departments,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        for dept in departments:
            session.add(
                RfpDepartmentSection(
                    ticket_id=ticket.id,
                    department_id=dept,
                    approval_status="pending",
                    draft_content=f"Draft for {dept}. {COMPLIANT}",
                    iteration_count=iteration,
                    key_aspects={"aspects": ["storage capacity"]},
                )
            )
        session.commit()
        return ticket.id


def _start(ticket_id: str, cfg: Settings) -> None:
    start_ticket_approval(ticket_id, cfg, build_rag_config(cfg), 2, env="test")


def _decide(engine: Engine, cfg: Settings, ticket_id: str, dept: str, action: str, actor: str = OWNER) -> None:
    with Session(engine) as session:
        RfpService(cfg, session).decide(ticket_id, dept, action=action, note=None, actor=actor)


# --------------------------------------------------------------------------- approve + finalize


def test_start_moves_ticket_to_waiting_for_approval(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)
    with Session(engine) as session:
        assert session.get(RfpTicket, ticket_id).status == "waiting_for_approval"  # type: ignore[union-attr]


def test_approve_single_section_finalizes(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)
    _decide(engine, cfg, ticket_id, "warehouse", "approve")

    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None and ticket.status == "done"
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.approval_status == "approved" and section.approver == OWNER
        document = session.exec(
            select(RfpFinalDocument).where(RfpFinalDocument.ticket_id == ticket_id)
        ).one()
        assert document.currency == "USD" and "warehouse" in document.sections


def test_approval_run_reports_summed_duration_and_output_preview(
    engine: Engine, settings: Settings
) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)
    _decide(engine, cfg, ticket_id, "warehouse", "approve")

    with Session(engine) as session:
        run = session.exec(
            select(AgentRun).where(AgentRun.agent_name == "trackflow-rfp-approval")
        ).one()
        steps = session.exec(select(AgentNodeStep).where(AgentNodeStep.run_id == run.id)).all()
        # (F) The run duration is the sum of step durations, not a hardcoded 0.
        assert run.duration_ms == sum(int(step.duration_ms or 0) for step in steps)
        # A completed run carries a truncated consolidated-document preview (D1), never blank.
        assert run.output_summary and "warehouse" in run.output_summary


def test_approval_is_branch_scoped(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse", "lastmile"])
    _start(ticket_id, cfg)

    _decide(engine, cfg, ticket_id, "warehouse", "approve")
    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None and ticket.status == "waiting_for_approval"  # not done: lastmile pending
        statuses = {
            s.department_id: s.approval_status
            for s in session.exec(select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id))
        }
        assert statuses == {"warehouse": "approved", "lastmile": "pending"}

    _decide(engine, cfg, ticket_id, "lastmile", "approve")
    with Session(engine) as session:
        assert session.get(RfpTicket, ticket_id).status == "done"  # type: ignore[union-attr]


def test_reject_blocks_finalize(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)
    _decide(engine, cfg, ticket_id, "warehouse", "reject")

    with Session(engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        assert ticket is not None and ticket.status == "waiting_for_approval"
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.approval_status == "rejected"
        assert session.exec(select(RfpFinalDocument).where(RfpFinalDocument.ticket_id == ticket_id)).all() == []


# --------------------------------------------------------------------------- request changes + cap


def test_request_changes_regenerates_then_approves(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"], iteration=1)
    _start(ticket_id, cfg)
    monkeypatch.setattr(rfp_approval, "draft_section", lambda *a, **k: ("Revised. " + COMPLIANT, None))

    _decide(engine, cfg, ticket_id, "warehouse", "request_changes")
    with Session(engine) as session:
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.approval_status == "pending"  # re-interrupted, awaiting a fresh decision
        assert section.iteration_count == 2
        assert section.draft_content is not None and section.draft_content.startswith("Revised.")

    _decide(engine, cfg, ticket_id, "warehouse", "approve")
    with Session(engine) as session:
        assert session.get(RfpTicket, ticket_id).status == "done"  # type: ignore[union-attr]


def test_request_changes_hits_iteration_cap(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    # Section already at the cap; a further request_changes must not loop.
    ticket_id = _seed_under_eval(engine, departments=["warehouse"], iteration=2)
    _start(ticket_id, cfg)
    _decide(engine, cfg, ticket_id, "warehouse", "request_changes")

    with Session(engine) as session:
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        assert section.approval_status == "changes_requested"  # exhausted, left for a human


# --------------------------------------------------------------------------- guards


def test_second_decision_is_conflict(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)
    _decide(engine, cfg, ticket_id, "warehouse", "approve")

    with Session(engine) as session, pytest.raises(RfpError) as exc:
        RfpService(cfg, session).decide(ticket_id, "warehouse", action="approve", note=None, actor=OWNER)
    assert exc.value.status_code == 409


def test_decide_other_owner_is_404(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"], owner=OTHER)
    _start(ticket_id, cfg)

    with Session(engine) as session, pytest.raises(RfpError) as exc:
        RfpService(cfg, session).decide(ticket_id, "warehouse", action="approve", note=None, actor=OWNER)
    assert exc.value.status_code == 404


def test_get_document_not_ready_is_404(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    with Session(engine) as session, pytest.raises(RfpError) as exc:
        RfpService(cfg, session).get_document(ticket_id, OWNER)
    assert exc.value.status_code == 404


# --------------------------------------------------------------------------- HTTP endpoints


def _enable(app: FastAPI, base: Settings) -> Settings:
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        rfp_enabled=True,
        openai_api_key="test-openai",
        deepseek_api_key="test-deepseek",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    return configured


def test_decision_endpoint_completes_and_serves_document(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    cfg = _enable(app, settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)

    response = client.post(
        f"/rfp/tickets/{ticket_id}/departments/warehouse/decision",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"

    document = client.get(f"/rfp/tickets/{ticket_id}/document", headers=auth_headers)
    assert document.status_code == 200
    assert document.json()["currency"] == "USD"


def test_document_download_returns_markdown_attachment(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    cfg = _enable(app, settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)
    client.post(
        f"/rfp/tickets/{ticket_id}/departments/warehouse/decision",
        json={"action": "approve"},
        headers=auth_headers,
    )

    response = client.get(f"/rfp/tickets/{ticket_id}/document/download", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; filename=")
    assert ".md" in disposition
    assert response.text.startswith("# RFP Proposal")


def test_document_pdf_returns_pdf_attachment(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _enable(app, settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])
    _start(ticket_id, cfg)
    client.post(
        f"/rfp/tickets/{ticket_id}/departments/warehouse/decision",
        json={"action": "approve"},
        headers=auth_headers,
    )
    # Mock WeasyPrint rendering so the test never needs the native Pango/cairo libraries.
    from central_api.domains.rfp import service as rfp_service

    monkeypatch.setattr(rfp_service, "render_final_document_pdf", lambda *_a, **_k: b"%PDF-1.7 mock")

    response = client.get(f"/rfp/tickets/{ticket_id}/document/pdf", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; filename=") and disposition.endswith('.pdf"')
    assert response.content.startswith(b"%PDF-")


def test_document_pdf_not_ready_is_404(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    _enable(app, settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])  # never finalized
    assert client.get(f"/rfp/tickets/{ticket_id}/document/pdf", headers=auth_headers).status_code == 404


def test_document_download_not_ready_is_404(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    _enable(app, settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"])  # never finalized
    response = client.get(f"/rfp/tickets/{ticket_id}/document/download", headers=auth_headers)
    assert response.status_code == 404


def test_document_download_other_owner_is_404(engine: Engine, settings: Settings) -> None:
    cfg = _configured(settings)
    ticket_id = _seed_under_eval(engine, departments=["warehouse"], owner=OTHER)
    _start(ticket_id, cfg)
    with Session(engine) as session, pytest.raises(RfpError) as exc:
        RfpService(cfg, session).get_document_markdown(ticket_id, OWNER)
    assert exc.value.status_code == 404


def test_decision_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/rfp/tickets/abc/departments/warehouse/decision", json={"action": "approve"}
    )
    assert response.status_code == 401


def test_decision_endpoint_rejects_invalid_action(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
) -> None:
    _enable(app, settings)
    response = client.post(
        "/rfp/tickets/abc/departments/warehouse/decision",
        json={"action": "maybe"},
        headers=auth_headers,
    )
    assert response.status_code == 422
