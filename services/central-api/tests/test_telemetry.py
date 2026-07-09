"""Telemetry reporting, best-effort emission, allowlisting, and retention pruning."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.core.config import Settings
from central_api.domains.telemetry.models import TelemetryEvent

TODAY = datetime.now(UTC).date().isoformat()


@pytest.fixture
def telemetry_on(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Settings:
    """Enable best-effort emission by pointing the recorder at telemetry-enabled settings."""
    enabled = settings.model_copy(update={"telemetry_enabled": True, "app_env": "test"})
    monkeypatch.setattr("central_api.domains.telemetry.recorder.get_settings", lambda: enabled)
    return enabled


def _events(engine: Engine, event: str | None = None) -> list[TelemetryEvent]:
    with Session(engine) as session:
        statement = select(TelemetryEvent)
        if event is not None:
            statement = statement.where(TelemetryEvent.event == event)
        return list(session.exec(statement).all())


def _dispatch(
    client: TestClient, headers: dict[str, str], sku_id: int, quantity: int, warehouse: str = "LA"
) -> None:
    body = {
        "sku_id": sku_id,
        "quantity": quantity,
        "exit_type": "dispatch",
        "tracking_number": "1Z999AA10123456784",
        "warehouse": warehouse,
    }
    response = client.post("/inventory/orders/outbound", json=body, headers=headers)
    assert response.status_code == 201, response.text


def _inbound(client: TestClient, headers: dict[str, str], sku_id: int, quantity: int, warehouse: str = "LA") -> None:
    body = {"sku_id": sku_id, "quantity": quantity, "reference": "PO-2026-1", "warehouse": warehouse}
    response = client.post("/inventory/orders/inbound", json=body, headers=headers)
    assert response.status_code == 201, response.text


# --- Reporting: authorization, validation, empty states -----------------------------------


def test_reporting_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/telemetry/metrics/dispatch?from={TODAY}&to={TODAY}")
    assert response.status_code == 401


def test_reporting_rejects_inverted_range(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/telemetry/metrics/dispatch?from=2026-07-10&to=2026-07-01", headers=auth_headers)
    assert response.status_code == 400


def test_reporting_rejects_excessive_range(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/telemetry/metrics/dispatch?from=2026-01-01&to=2026-12-31", headers=auth_headers)
    assert response.status_code == 400


def test_reporting_requires_dates(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/telemetry/metrics/dispatch", headers=auth_headers)
    assert response.status_code == 422


def test_empty_range_returns_period_and_no_rows(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(f"/telemetry/metrics/dispatch?from={TODAY}&to={TODAY}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == {"from": TODAY, "to": TODAY}
    assert body["rows"] == []


# --- Exact metrics come from the durable business tables ----------------------------------


def test_exact_dispatch_receiving_and_loss_metrics(
    client: TestClient, auth_headers: dict[str, str], created_product: dict[str, object]
) -> None:
    sku_id = int(created_product["id"])  # type: ignore[call-overload]
    _inbound(client, auth_headers, sku_id, 100)
    _dispatch(client, auth_headers, sku_id, 10)
    _dispatch(client, auth_headers, sku_id, 5)
    loss = {"sku_id": sku_id, "quantity": 3, "exit_type": "loss", "tracking_number": None, "warehouse": "LA"}
    assert client.post("/inventory/orders/outbound", json=loss, headers=auth_headers).status_code == 201

    dispatch = client.get(f"/telemetry/metrics/dispatch?from={TODAY}&to={TODAY}", headers=auth_headers).json()
    assert dispatch["rows"] == [
        {"date": TODAY, "warehouse": "LA", "dispatched": 2, "rejected": 0, "indicative_failure_rate": 0.0}
    ]

    receiving = client.get(f"/telemetry/metrics/receiving?from={TODAY}&to={TODAY}", headers=auth_headers).json()
    assert receiving["rows"] == [{"date": TODAY, "warehouse": "LA", "count": 1}]

    stock_loss = client.get(f"/telemetry/metrics/stock-loss?from={TODAY}&to={TODAY}", headers=auth_headers).json()
    assert stock_loss["rows"] == [{"date": TODAY, "warehouse": "LA", "count": 1, "units": 3}]


# --- Best-effort diagnostics: dispatch rejections ------------------------------------------


def test_rejected_dispatch_emits_one_diagnostic_and_feeds_metric(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    engine: Engine,
    telemetry_on: Settings,
) -> None:
    sku_id = int(created_product["id"])  # type: ignore[call-overload]
    _inbound(client, auth_headers, sku_id, 5)
    # Requesting more than available is rejected with 400 and no StockExit is written.
    response = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 50,
            "exit_type": "dispatch",
            "tracking_number": "1Z999AA10123456784",
            "warehouse": "LA",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400

    rows = _events(engine, "inventory.dispatch.rejected")
    assert len(rows) == 1
    row = rows[0]
    assert row.category == "operational"
    assert row.warehouse == "LA"
    assert row.reason_code == "INSUFFICIENT_STOCK"
    assert row.value == 50
    # Allowlist: only the declared keys are ever stored.
    assert set(row.properties) <= {"warehouse", "reason_code", "quantity"}

    metric = client.get(f"/telemetry/metrics/dispatch?from={TODAY}&to={TODAY}", headers=auth_headers).json()
    assert metric["rows"] == [
        {"date": TODAY, "warehouse": "LA", "dispatched": 0, "rejected": 1, "indicative_failure_rate": 1.0}
    ]


def test_rejected_loss_does_not_emit_dispatch_diagnostic(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    engine: Engine,
    telemetry_on: Settings,
) -> None:
    sku_id = int(created_product["id"])  # type: ignore[call-overload]
    response = client.post(
        "/inventory/orders/outbound",
        json={"sku_id": sku_id, "quantity": 9, "exit_type": "loss", "tracking_number": None, "warehouse": "LA"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert _events(engine, "inventory.dispatch.rejected") == []


def test_disabled_telemetry_emits_nothing(
    client: TestClient, auth_headers: dict[str, str], created_product: dict[str, object], engine: Engine
) -> None:
    sku_id = int(created_product["id"])  # type: ignore[call-overload]
    response = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 50,
            "exit_type": "dispatch",
            "tracking_number": "1Z999AA10123456784",
            "warehouse": "LA",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert _events(engine) == []


def test_business_write_succeeds_even_if_emitter_raises(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    telemetry_on: Settings,
) -> None:
    sku_id = int(created_product["id"])  # type: ignore[call-overload]

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("sink down")

    monkeypatch.setattr("central_api.domains.telemetry.recorder._record", boom)
    # A committed dispatch must still succeed even though the background emitter throws.
    _inbound(client, auth_headers, sku_id, 20)
    _dispatch(client, auth_headers, sku_id, 5)


# --- Best-effort diagnostics: API access denials -------------------------------------------


def test_unauthenticated_request_emits_access_denied(
    client: TestClient, engine: Engine, telemetry_on: Settings
) -> None:
    response = client.get("/inventory/products")
    assert response.status_code == 401
    rows = _events(engine, "api.access.denied")
    assert len(rows) == 1
    assert rows[0].category == "security"
    assert rows[0].reason_code == "unauthenticated"
    assert rows[0].warehouse is None
    assert set(rows[0].properties) == {"reason"}


def test_csrf_denied_write_emits_access_denied(
    client: TestClient,
    engine: Engine,
    cookie_auth: Callable[..., dict[str, str]],
    product_payload: dict[str, object],
    telemetry_on: Settings,
) -> None:
    headers = cookie_auth(csrf=False)  # cookie set, no CSRF header
    response = client.post("/inventory/products", json=product_payload, headers=headers)
    assert response.status_code == 403
    rows = _events(engine, "api.access.denied")
    assert [row.reason_code for row in rows] == ["csrf"]


def test_failed_login_is_not_a_telemetry_event(client: TestClient, engine: Engine, telemetry_on: Settings) -> None:
    # There is no login on Central API; auth failures here are access denials, never
    # "login" rows. Login auditing is Identity-owned logs (see identity tests).
    client.get("/inventory/products")
    assert all(row.event == "api.access.denied" for row in _events(engine))


# --- Retention pruning ---------------------------------------------------------------------


def test_prune_respects_category_windows(engine: Engine) -> None:
    from central_api.domains.telemetry.service import TelemetryService

    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(
            TelemetryEvent(
                event="inventory.dispatch.rejected",
                category="operational",
                occurred_at=now - timedelta(days=120),
                service="central-api",
                env="test",
                severity="warning",
                warehouse="LA",
                reason_code="INSUFFICIENT_STOCK",
                value=1,
                properties={"warehouse": "LA", "reason_code": "INSUFFICIENT_STOCK"},
            )
        )
        session.add(
            TelemetryEvent(
                event="api.access.denied",
                category="security",
                occurred_at=now - timedelta(days=120),
                service="central-api",
                env="test",
                severity="warning",
                reason_code="unauthenticated",
                properties={"reason": "unauthenticated"},
            )
        )
        session.commit()

    with Session(engine) as session:
        deleted = TelemetryService(session).prune(
            operational_cutoff=now - timedelta(days=90),
            security_cutoff=now - timedelta(days=365),
        )
    # 120-day operational row is past its 90-day window; the security row (365d) survives.
    assert deleted == {"operational": 1, "security": 0}
    remaining = _events(engine)
    assert [row.category for row in remaining] == ["security"]
