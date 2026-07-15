"""Reporting endpoint contracts, security boundaries, and safe failure responses."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from central_api.domains.inventory.models import Client
from central_api.domains.reporting.models import IncompleteWeek, PipelineRun, WeeklyWarehouseClientPerformance
from central_api.domains.reporting.repository import ReportingRepository
from central_api.domains.reporting.service import ReportingService

MONDAY = date(2026, 7, 13)
NEXT_MONDAY = date(2026, 7, 20)
BASE_TIME = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def _client(session: Session, name: str) -> Client:
    client = Client(display_name=name)
    session.add(client)
    session.flush()
    return client


def _report(session: Session, client: Client, week_start: date, *, warehouse: str = "los_angeles") -> None:
    session.add(
        WeeklyWarehouseClientPerformance(
            warehouse=warehouse,
            client_id=client.id,
            week_start=week_start,
            inbound_units_count=4200,
            outbound_orders_count=980,
            stockout_events_count=3,
            discrepancy_events_count=2,
            discrepancy_rate=Decimal("0.002"),
        )
    )


def _run(
    *,
    status: str,
    requested_at: datetime,
    target_weeks: list[date] | None = None,
    trigger_type: str = "scheduled",
    requested_by: str = "system",
    finished_at: datetime | None = None,
    rows_loaded: int | None = None,
    error_code: str | None = None,
) -> PipelineRun:
    return PipelineRun(
        pipeline_name="business_performance",
        trigger_type=trigger_type,
        requested_by=requested_by,
        requested_at=requested_at,
        target_weeks=target_weeks,
        status=status,
        attempt=1,
        started_at=requested_at + timedelta(minutes=1) if status != "requested" else None,
        finished_at=finished_at,
        rows_loaded=rows_loaded,
        error_code=error_code,
    )


def test_weekly_report_explicit_week_join_order_and_incomplete_flag(
    client: TestClient,
    auth_headers: dict[str, str],
    engine: Engine,
) -> None:
    with Session(engine) as session:
        zulu = _client(session, "Zulu Brand")
        alpha = _client(session, "Alpha Brand")
        _report(session, zulu, MONDAY, warehouse="zaragoza")
        _report(session, zulu, MONDAY)
        _report(session, alpha, MONDAY)
        session.add(IncompleteWeek(week_start=MONDAY, reason="ledger_reset"))
        session.commit()
        alpha_id = alpha.id

    response = client.get(
        "/reporting/weekly-warehouse-client-performance",
        params={"week_start": MONDAY.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["week_start"] == MONDAY.isoformat()
    assert payload["incomplete"] is True
    assert [(row["warehouse"], row["client_name"]) for row in payload["entries"]] == [
        ("los_angeles", "Alpha Brand"),
        ("los_angeles", "Zulu Brand"),
        ("zaragoza", "Zulu Brand"),
    ]
    assert payload["entries"][0]["client_id"] == str(alpha_id)
    assert payload["entries"][0]["discrepancy_rate"] == 0.002


@pytest.mark.parametrize("value", ["not-a-date", "2026-07-14"])
def test_weekly_report_rejects_invalid_week_with_stable_code(
    client: TestClient,
    auth_headers: dict[str, str],
    value: str,
) -> None:
    response = client.get(
        "/reporting/weekly-warehouse-client-performance",
        params={"week_start": value},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REPORTING_INVALID_WEEK_START"


def test_weekly_report_default_requires_latest_touching_success(
    client: TestClient,
    auth_headers: dict[str, str],
    engine: Engine,
) -> None:
    with Session(engine) as session:
        brand = _client(session, "Fashion Co")
        _report(session, brand, MONDAY)
        _report(session, brand, NEXT_MONDAY)
        session.add(_run(status="succeeded", requested_at=BASE_TIME, target_weeks=[MONDAY], finished_at=BASE_TIME))
        session.add(
            _run(
                status="succeeded",
                requested_at=BASE_TIME + timedelta(hours=1),
                target_weeks=[NEXT_MONDAY],
                finished_at=BASE_TIME + timedelta(hours=1),
            )
        )
        session.add(
            _run(
                status="failed",
                requested_at=BASE_TIME + timedelta(hours=2),
                target_weeks=[NEXT_MONDAY],
                finished_at=BASE_TIME + timedelta(hours=2),
                error_code="LOAD_FAILED",
            )
        )
        session.commit()

    response = client.get("/reporting/weekly-warehouse-client-performance", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["week_start"] == MONDAY.isoformat()


def test_weekly_report_empty_states_and_authentication(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    assert client.get("/reporting/weekly-warehouse-client-performance").status_code == 401
    empty = client.get("/reporting/weekly-warehouse-client-performance", headers=auth_headers)
    assert empty.json() == {"week_start": None, "incomplete": False, "entries": []}
    requested = client.get(
        "/reporting/weekly-warehouse-client-performance",
        params={"week_start": MONDAY.isoformat()},
        headers=auth_headers,
    )
    assert requested.json() == {"week_start": MONDAY.isoformat(), "incomplete": False, "entries": []}


def test_latest_runs_distinguishes_latest_success_and_queue_without_internals(
    client: TestClient,
    auth_headers: dict[str, str],
    engine: Engine,
) -> None:
    with Session(engine) as session:
        success = _run(
            status="succeeded",
            requested_at=BASE_TIME,
            target_weeks=[MONDAY],
            finished_at=BASE_TIME + timedelta(minutes=5),
            rows_loaded=24,
        )
        latest = _run(
            status="failed",
            requested_at=BASE_TIME + timedelta(hours=1),
            finished_at=BASE_TIME + timedelta(hours=1, minutes=5),
            error_code="LOAD_FAILED",
        )
        latest.cache_nonce = uuid4()
        queued = _run(
            status="requested",
            requested_at=BASE_TIME + timedelta(minutes=30),
            trigger_type="manual",
            requested_by=str(uuid4()),
        )
        retryable = _run(
            status="retryable",
            requested_at=BASE_TIME + timedelta(minutes=45),
            trigger_type="manual",
            requested_by=str(uuid4()),
            error_code="DB_UNAVAILABLE",
        )
        retryable.cache_nonce = uuid4()
        session.add_all([success, queued, retryable, latest])
        session.commit()
        latest_id = latest.id
        success_id = success.id

    response = client.get("/reporting/pipeline-runs/latest", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["latest"]["run_id"] == str(latest_id)
    assert payload["latest"]["status"] == "failed"
    assert payload["latest"]["error_code"] == "LOAD_FAILED"
    assert payload["latest_successful"] == {
        "run_id": str(success_id),
        "finished_at": (BASE_TIME + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "target_weeks": [MONDAY.isoformat()],
        "rows_loaded": 24,
    }
    assert payload["worker"] == {"status": "unknown", "last_seen_at": None}
    assert [item["trigger_type"] for item in payload["queued"]] == ["manual", "manual"]
    serialized = response.text.lower()
    for forbidden in ("cache_nonce", "bucket", "object_key", "claim_token", "lease_expires_at"):
        assert forbidden not in serialized


def test_latest_runs_empty_state(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/reporting/pipeline-runs/latest", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["latest"] is None
    assert payload["latest_successful"] is None
    assert payload["queued"] == []
    assert payload["worker"] == {"status": "unknown", "last_seen_at": None}


def test_latest_runs_reports_worker_health(
    client: TestClient,
    auth_headers: dict[str, str],
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    monkeypatch.setattr("central_api.domains.reporting.service.utc_now", lambda: now)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reporting.worker_heartbeats (worker_name, heartbeat_at) "
                "VALUES ('reporting', :heartbeat_at)"
            ),
            {"heartbeat_at": now - timedelta(seconds=10)},
        )
    healthy = client.get("/reporting/pipeline-runs/latest", headers=auth_headers)
    assert healthy.json()["worker"] == {
        "status": "healthy",
        "last_seen_at": (now - timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
    }

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE reporting.worker_heartbeats SET heartbeat_at = :heartbeat_at"),
            {"heartbeat_at": now - timedelta(seconds=31)},
        )
    stale = client.get("/reporting/pipeline-runs/latest", headers=auth_headers)
    assert stale.json()["worker"]["status"] == "stale"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 1, 15, 13, 1, tzinfo=UTC), datetime(2026, 1, 16, 13, 0, tzinfo=UTC)),
        (datetime(2026, 7, 15, 12, 1, tzinfo=UTC), datetime(2026, 7, 16, 12, 0, tzinfo=UTC)),
    ],
)
def test_next_refresh_uses_cst_and_cdt(now: datetime, expected: datetime) -> None:
    assert ReportingService._next_refresh(now).next_occurrence_utc == expected


def test_manual_trigger_enforces_admin_auth_and_csrf(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
    cookie_auth: Callable[..., dict[str, str]],
) -> None:
    assert client.post("/reporting/pipeline-runs", json={}).status_code == 401
    forbidden = client.post("/reporting/pipeline-runs", json={}, headers=auth_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "REPORTING_FORBIDDEN"
    client.cookies.clear()
    cookie_auth(csrf=False, role="admin")
    assert client.post("/reporting/pipeline-runs", json={}).status_code == 403
    client.cookies.clear()
    accepted = client.post("/reporting/pipeline-runs", json={}, headers=admin_headers)
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "requested"


def test_manual_trigger_persists_week_rejects_invalid_and_frozen(
    client: TestClient,
    admin_headers: dict[str, str],
    engine: Engine,
) -> None:
    accepted = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": MONDAY.isoformat()},
        headers=admin_headers,
    )
    assert accepted.status_code == 202
    with engine.connect() as connection:
        persisted = connection.execute(
            text("SELECT requested_week_start FROM reporting.pipeline_runs WHERE id = :id"),
            {"id": UUID(accepted.json()["run_id"])},
        ).scalar_one()
    assert persisted == MONDAY

    invalid = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": "2026-07-14"},
        headers=admin_headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "REPORTING_INVALID_WEEK_START"

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE reporting.source_ledger_state SET last_reset_at = :reset_at WHERE id = 1"),
            {"reset_at": datetime(2026, 7, 14, tzinfo=UTC)},
        )
    frozen = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": MONDAY.isoformat(), "force_refresh": True},
        headers=admin_headers,
    )
    assert frozen.status_code == 400
    assert frozen.json()["error"]["code"] == "REPORTING_WEEK_FROZEN"


def test_reporting_database_failures_are_safe(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = OperationalError("SELECT secret_payload", {}, RuntimeError("database-password"))
    monkeypatch.setattr(ReportingRepository, "default_week_start", lambda _self: (_ for _ in ()).throw(failure))
    response = client.get("/reporting/weekly-warehouse-client-performance", headers=auth_headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REPORTING_UNAVAILABLE"
    assert "secret_payload" not in response.text
    assert "database-password" not in response.text

    monkeypatch.undo()
    monkeypatch.setattr(ReportingRepository, "latest_run", lambda _self: (_ for _ in ()).throw(failure))
    latest = client.get("/reporting/pipeline-runs/latest", headers=auth_headers)
    assert latest.status_code == 503
    assert latest.json()["error"]["code"] == "REPORTING_UNAVAILABLE"
    assert "secret_payload" not in latest.text

    monkeypatch.undo()
    monkeypatch.setattr(
        "central_api.domains.reporting.service.enqueue_manual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    queued = client.post("/reporting/pipeline-runs", json={}, headers=admin_headers)
    assert queued.status_code == 503
    assert "secret_payload" not in queued.text
