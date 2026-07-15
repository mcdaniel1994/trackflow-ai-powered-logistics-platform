"""Central API integration with the data package's durable reporting queue."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from pipelines.business_performance.queue import RunMetrics, claim_next, enqueue_cli, finalize_success
from sqlalchemy import Engine, text

from central_api.domains.reporting.service import ReportingService

MONDAY = date(2026, 7, 13)
BASE_TIME = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def _row(engine: Engine, run_id: UUID) -> dict[str, object]:
    with engine.connect() as connection:
        return dict(
            connection.execute(
                text("SELECT * FROM reporting.pipeline_runs WHERE id = :id"),
                {"id": run_id},
            ).mappings().one()
        )


def test_api_queue_coalesces_non_forced_and_keeps_force_refresh_distinct(engine: Engine) -> None:
    from sqlmodel import Session

    with Session(engine) as session:
        service = ReportingService(session)
        first = service.request_run(
            week_start=MONDAY.isoformat(), force_refresh=False, requested_by="admin-1", role="admin"
        )
        duplicate = service.request_run(
            week_start=MONDAY.isoformat(), force_refresh=False, requested_by="admin-2", role="admin"
        )
        forced = service.request_run(
            week_start=MONDAY.isoformat(), force_refresh=True, requested_by="admin-3", role="admin"
        )
    assert first.run_id == duplicate.run_id
    assert forced.run_id != first.run_id
    assert _row(engine, first.run_id)["cache_nonce"] is None
    assert _row(engine, forced.run_id)["cache_nonce"] is not None


def test_api_request_queues_behind_active_and_survives_new_session_claim(engine: Engine) -> None:
    from sqlmodel import Session

    active_id = enqueue_cli(engine, now=BASE_TIME - timedelta(minutes=1))
    active = claim_next(engine, now=BASE_TIME)
    assert active is not None and active.run_id == active_id

    with Session(engine) as first_session:
        accepted = ReportingService(first_session).request_run(
            week_start=MONDAY.isoformat(),
            force_refresh=False,
            requested_by="11111111-1111-4111-8111-111111111111",
            role="admin",
        )
    assert _row(engine, accepted.run_id)["status"] == "requested"

    assert finalize_success(engine, active, RunMetrics(0, 0, 0), now=BASE_TIME + timedelta(minutes=1))
    # A fresh claim has no request-memory from the API process; the persisted week
    # remains the sole source of truth after this restart-style boundary.
    claimed = claim_next(engine, now=BASE_TIME + timedelta(minutes=2))
    assert claimed is not None
    assert claimed.run_id == accepted.run_id
    assert claimed.requested_week_start == MONDAY
    assert claimed.target_weeks == (MONDAY,)
