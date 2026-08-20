"""Demo-incident seeder: idempotency, coverage, and determinism."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from trackflow_incidents import Branch, IncidentCategory, IncidentOrigin, IncidentStatus

from central_api.domains.incidents.demo_seed import (
    HISTORY_DAYS,
    INCIDENT_COUNT,
    build_demo_incidents,
    seed_demo_incidents,
)
from central_api.domains.incidents.models import Incident

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


@pytest.fixture()
def session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as active:
        yield active


def _rows(session: Session) -> list[Incident]:
    return list(session.exec(select(Incident).order_by(Incident.id)).all())


def test_seed_is_idempotent_via_the_count_guard(session: Session) -> None:
    first = seed_demo_incidents(session, now=NOW)
    assert first.inserted == INCIDENT_COUNT
    assert first.skipped is False

    second = seed_demo_incidents(session, now=NOW)
    assert second.inserted == 0
    assert second.skipped is True
    assert second.existing == INCIDENT_COUNT
    assert len(_rows(session)) == INCIDENT_COUNT


def test_seed_covers_every_status_category_origin_and_branch(session: Session) -> None:
    """The dashboard's filters and summary tiles are only meaningful if each
    dimension is actually populated."""
    seed_demo_incidents(session, now=NOW)
    rows = _rows(session)

    assert {row.status for row in rows} == {s.value for s in IncidentStatus}
    assert {row.category for row in rows} == {c.value for c in IncidentCategory}
    assert {row.origin for row in rows} == {o.value for o in IncidentOrigin}
    assert {row.branch for row in rows} == {b.value for b in Branch}


def test_timestamps_stay_inside_the_history_window(session: Session) -> None:
    seed_demo_incidents(session, now=NOW)
    earliest = NOW - timedelta(days=HISTORY_DAYS)

    for row in _rows(session):
        assert earliest <= row.created_at <= NOW
        # An update can never precede creation, nor overtake the clock.
        assert row.created_at <= row.updated_at <= NOW


def test_open_incidents_are_untouched_and_terminal_ones_are_not(session: Session) -> None:
    """Status and timestamps must tell the same story: an open incident has never
    been worked, a resolved one has."""
    seed_demo_incidents(session, now=NOW)
    rows = _rows(session)

    for row in rows:
        if row.status == IncidentStatus.OPEN.value:
            assert row.updated_at == row.created_at
        elif row.status in {IncidentStatus.RESOLVED.value, IncidentStatus.DISCARDED.value}:
            assert row.updated_at > row.created_at


def test_generation_is_deterministic() -> None:
    """A fixed seed means a rerun against an empty database reproduces the same
    rows, so the demo data is reviewable rather than arbitrary."""
    first = build_demo_incidents(NOW, None)
    second = build_demo_incidents(NOW, None)

    assert [(row.title, row.category, row.status, row.branch) for row in first] == [
        (row.title, row.category, row.status, row.branch) for row in second
    ]
    assert [row.import_key_hash for row in first] == [row.import_key_hash for row in second]


def test_import_keys_are_unique_and_namespaced_away_from_the_csv_importer() -> None:
    """The legacy importer hashes a bare incident id; a collision would make one
    seeder silently skip the other's rows."""
    incidents = build_demo_incidents(NOW, None)
    keys = [row.import_key_hash for row in incidents]

    assert len(set(keys)) == len(keys)
    assert all(key is not None and len(key) == 64 for key in keys)


def test_seed_runs_when_a_few_incidents_already_exist(session: Session) -> None:
    """The guard is a threshold, not a "table must be empty" check: a handful of
    manually created incidents should not block the demo data."""
    session.add(
        Incident(
            title="Manually filed incident",
            description="Created through the API before seeding.",
            category=IncidentCategory.OTHER.value,
            status=IncidentStatus.OPEN.value,
            origin=IncidentOrigin.INTERNAL.value,
            branch=Branch.CENTRAL.value,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.commit()

    result = seed_demo_incidents(session, now=NOW)
    assert result.existing == 1
    assert result.inserted == INCIDENT_COUNT


def test_attribution_is_applied_when_a_seed_user_is_supplied(session: Session) -> None:
    """Delegated OAuth principals only see their own incidents, so attribution
    decides whether the demo data is visible to them at all."""
    uuid = "11111111-1111-4111-8111-111111111111"
    seed_demo_incidents(session, now=NOW, user_uuid=uuid)

    assert {row.created_by_user_uuid for row in _rows(session)} == {uuid}


def test_rows_satisfy_the_database_check_constraints(session: Session) -> None:
    """The seeder bypasses IncidentService, so the CHECK constraints are the only
    validation left. Prove they actually accepted every row."""
    seed_demo_incidents(session, now=NOW)

    total = session.scalar(text("SELECT count(*) FROM incidents"))
    assert int(total or 0) == INCIDENT_COUNT
