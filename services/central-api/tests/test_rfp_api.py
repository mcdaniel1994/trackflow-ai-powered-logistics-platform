"""Endpoint + persistence tests for the Engagement 9 RFP workflow (Phase 0 scaffolding).

Covers the feature gate (503 when disabled), authentication, owner-scoped reads, the ticket detail
projection with department sections, and the repository. No provider or graph is involved yet.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.core.config import Settings, get_settings
from central_api.domains.rfp.config import is_rfp_configured
from central_api.domains.rfp.models import RfpDepartmentSection, RfpTicket
from central_api.domains.rfp.repository import RfpRepository

OWNER = "11111111-1111-4111-8111-111111111111"  # matches the default token_factory subject
OTHER_OWNER = "22222222-2222-4222-8222-222222222222"


def _enable_rfp(app: FastAPI, base: Settings) -> Settings:
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        rfp_enabled=True,
    )
    app.dependency_overrides[get_settings] = lambda: configured
    return configured


def _seed_ticket(
    engine: Engine,
    *,
    rfp_id: str,
    owner: str = OWNER,
    status: str = "analyzing",
    with_section: bool = False,
) -> str:
    with Session(engine) as session:
        ticket = RfpTicket(
            rfp_id=rfp_id,
            status=status,
            owner_user_uuid=owner,
            client_name="Luna Cosmetics",
            client_country="US",
            currency="USD",
            departments_needed=["warehouse", "lastmile"],
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        ticket_id = ticket.id
        if with_section:
            session.add(
                RfpDepartmentSection(
                    ticket_id=ticket_id,
                    department_id="warehouse",
                    approval_status="pending",
                    key_aspects={"capacity": "safe-metadata-only"},
                )
            )
            session.commit()
    return ticket_id


# --------------------------------------------------------------------------- feature gate + auth


def test_list_requires_authentication(client: TestClient) -> None:
    assert client.get("/rfp/tickets").status_code == 401


def test_list_unavailable_when_disabled(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Default test settings leave the RFP workflow disabled.
    assert client.get("/rfp/tickets", headers=auth_headers).status_code == 503


def test_get_unavailable_when_disabled(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/rfp/tickets/anything", headers=auth_headers).status_code == 503


# --------------------------------------------------------------------------- owner-scoped reads


def test_list_returns_only_owner_tickets(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    _enable_rfp(app, settings)
    _seed_ticket(engine, rfp_id="RFP-MINE")
    _seed_ticket(engine, rfp_id="RFP-THEIRS", owner=OTHER_OWNER)

    response = client.get("/rfp/tickets", headers=auth_headers)

    assert response.status_code == 200
    rfp_ids = [row["rfp_id"] for row in response.json()]
    assert rfp_ids == ["RFP-MINE"]


def test_list_filters_by_status(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    _enable_rfp(app, settings)
    _seed_ticket(engine, rfp_id="RFP-A", status="analyzing")
    _seed_ticket(engine, rfp_id="RFP-D", status="done")

    response = client.get("/rfp/tickets", params={"status": "done"}, headers=auth_headers)

    assert response.status_code == 200
    assert [row["rfp_id"] for row in response.json()] == ["RFP-D"]


def test_get_ticket_returns_detail_with_sections(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    _enable_rfp(app, settings)
    ticket_id = _seed_ticket(engine, rfp_id="RFP-DETAIL", with_section=True)

    response = client.get(f"/rfp/tickets/{ticket_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["rfp_id"] == "RFP-DETAIL"
    assert body["currency"] == "USD"
    assert [section["department_id"] for section in body["sections"]] == ["warehouse"]


def test_get_other_owner_ticket_is_404(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    _enable_rfp(app, settings)
    ticket_id = _seed_ticket(engine, rfp_id="RFP-HIDDEN", owner=OTHER_OWNER)

    # Owner scoping means another user's ticket is indistinguishable from a missing one.
    assert client.get(f"/rfp/tickets/{ticket_id}", headers=auth_headers).status_code == 404


def test_get_missing_ticket_is_404(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
) -> None:
    _enable_rfp(app, settings)
    assert client.get("/rfp/tickets/does-not-exist", headers=auth_headers).status_code == 404


# --------------------------------------------------------------------------- config + repository


def test_is_rfp_configured_reflects_flag(settings: Settings) -> None:
    assert is_rfp_configured(settings) is False
    assert is_rfp_configured(Settings(database_url=settings.database_url, rfp_enabled=True)) is True


def test_repository_add_and_reads(engine: Engine) -> None:
    with Session(engine) as session:
        repo = RfpRepository(session)
        created = repo.add_ticket(RfpTicket(rfp_id="RFP-REPO", status="analyzing", owner_user_uuid=OWNER))
        assert created.id
        assert [t.rfp_id for t in repo.list_for_owner(OWNER)] == ["RFP-REPO"]
        assert repo.get_for_owner(created.id, OWNER) is not None
        assert repo.get_for_owner(created.id, OTHER_OWNER) is None
        assert repo.final_document(created.id) is None
        assert repo.sections_for_ticket(created.id) == []
