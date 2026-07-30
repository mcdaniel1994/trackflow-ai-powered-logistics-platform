"""Fail-closed startup contract for the reporting worker.

Compose no longer gates reporting-worker on the one-shot Prefect guards, so
these assertions are the only thing standing between a mis-deployed Prefect and
a worker that processes against it.
"""

from __future__ import annotations

import pytest

from pipelines.business_performance import startup_guard
from pipelines.business_performance.startup_guard import StartupGuardFailure, verify_startup_contract

APPROVED_SERVER = (
    "prefecthq/prefect:3.7.8-python3.11@sha256:"
    "d4d142f1426ed0e8d7f48b3cc730f7b0469dcbcaf720959bb678f4cec3e5c3cc"
)
# A password full of URL-reserved characters: the guard must never string-build a DSN.
HOSTILE_PASSWORD = "p@ss:w/rd+with=reserved"


@pytest.fixture(autouse=True)
def clean_pipeline_tables() -> None:
    """Override the package-wide database fixture: these are pure unit tests."""
    return None


@pytest.fixture
def approved_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREFECT_SERVER_IMAGE_REF", APPROVED_SERVER)
    monkeypatch.setenv("PREFECT_GUARD_DB_HOST", "prefect-postgres")
    monkeypatch.setenv("PREFECT_GUARD_DB_PORT", "5432")
    monkeypatch.setenv("PREFECT_GUARD_DB_NAME", "prefect")
    monkeypatch.setenv("PREFECT_GUARD_DB_USER", "prefect_guard")
    monkeypatch.setenv("PREFECT_GUARD_DB_PASSWORD", HOSTILE_PASSWORD)


def _probe_returning(*reasons: str | None):
    """Yield each reason in turn so retry behaviour is observable."""
    remaining = list(reasons)

    def probe(_url: object, *, budget_seconds: float) -> str | None:
        return remaining.pop(0) if remaining else None

    return probe


def test_passes_when_prefect_is_migrated_and_version_compatible(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(startup_guard, "_probe_prefect_database", _probe_returning(None))
    verify_startup_contract(timeout_seconds=5, interval_seconds=0)


def test_rejects_a_server_digest_that_is_not_approved(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PREFECT_SERVER_IMAGE_REF", f"prefecthq/prefect:3.7.8-python3.11@sha256:{'0' * 64}")
    with pytest.raises(StartupGuardFailure) as failure:
        verify_startup_contract(timeout_seconds=0, interval_seconds=0)
    assert failure.value.reason == "server_digest_not_approved"


def test_rejects_a_malformed_server_image_reference(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PREFECT_SERVER_IMAGE_REF", "prefecthq/prefect:latest")
    with pytest.raises(StartupGuardFailure) as failure:
        verify_startup_contract(timeout_seconds=0, interval_seconds=0)
    assert failure.value.reason == "server_image_reference_invalid"


def test_version_check_runs_before_any_database_access(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A static mismatch must fail immediately rather than after a retry loop."""

    def explode(_url: object, *, budget_seconds: float) -> str | None:
        raise AssertionError("database must not be probed when the version check fails")

    monkeypatch.setattr(startup_guard, "_probe_prefect_database", explode)
    monkeypatch.setenv("PREFECT_SERVER_IMAGE_REF", "prefecthq/prefect:latest")
    with pytest.raises(StartupGuardFailure):
        verify_startup_contract(timeout_seconds=30, interval_seconds=0)


def test_rejects_missing_guard_database_configuration(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PREFECT_GUARD_DB_PASSWORD", "")
    with pytest.raises(StartupGuardFailure) as failure:
        verify_startup_contract(timeout_seconds=0, interval_seconds=0)
    assert failure.value.reason == "guard_database_config_missing"


def test_password_with_reserved_characters_survives_url_building(approved_env: None) -> None:
    """@ : / + and = in a password must not corrupt the DSN or leak into its text."""
    url = startup_guard.guard_database_url()
    assert url.password == HOSTILE_PASSWORD
    assert url.username == "prefect_guard"
    assert url.host == "prefect-postgres"
    assert url.database == "prefect"
    # SQLAlchemy masks the password in str(); the real value round-trips intact.
    assert HOSTILE_PASSWORD not in str(url)


def test_rejects_a_non_numeric_guard_port(approved_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREFECT_GUARD_DB_PORT", "not-a-port")
    with pytest.raises(StartupGuardFailure) as failure:
        verify_startup_contract(timeout_seconds=0, interval_seconds=0)
    assert failure.value.reason == "guard_database_config_invalid"


def test_classifies_a_blocked_query_distinctly_from_an_unreachable_server(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """statement_timeout cancellation must be its own fixed, safe reason."""
    monkeypatch.setattr(
        startup_guard, "_probe_prefect_database", _probe_returning("prefect_database_query_timeout")
    )
    with pytest.raises(StartupGuardFailure) as failure:
        verify_startup_contract(timeout_seconds=0, interval_seconds=0)
    assert failure.value.reason == "prefect_database_query_timeout"


def test_probe_budget_never_exceeds_the_remaining_deadline(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single probe must not be able to outlive the overall guard timeout."""
    budgets: list[float] = []

    def probe(_url: object, *, budget_seconds: float) -> str | None:
        budgets.append(budget_seconds)
        return "flow_run_table_missing"

    monkeypatch.setattr(startup_guard, "_probe_prefect_database", probe)
    clock = iter([0.0, 0.0, 5.0, 5.0, 11.0, 11.0])
    with pytest.raises(StartupGuardFailure):
        verify_startup_contract(
            timeout_seconds=10,
            interval_seconds=0,
            monotonic=lambda: next(clock),
            sleep=lambda _s: None,
        )
    assert budgets == [10.0, 5.0]  # shrinks with the remaining deadline


def test_rejects_prefect_that_fell_back_off_postgres(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(startup_guard, "_probe_prefect_database", _probe_returning("pg_trgm_missing"))
    with pytest.raises(StartupGuardFailure) as failure:
        verify_startup_contract(timeout_seconds=0, interval_seconds=0)
    assert failure.value.reason == "pg_trgm_missing"


def test_retries_while_the_server_is_still_migrating(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """prefect-server reports healthy before flow_run necessarily exists."""
    monkeypatch.setattr(
        startup_guard,
        "_probe_prefect_database",
        _probe_returning("flow_run_table_missing", "flow_run_table_missing", None),
    )
    verify_startup_contract(timeout_seconds=30, interval_seconds=0)


def test_gives_up_at_the_deadline_rather_than_hanging(
    approved_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unbounded wait here would recreate the failure this change removes."""
    clock = iter([0.0, 1.0, 2.0, 99.0, 99.0])
    monkeypatch.setattr(
        startup_guard, "_probe_prefect_database", lambda _url, *, budget_seconds: "flow_run_table_missing"
    )
    with pytest.raises(StartupGuardFailure) as failure:
        verify_startup_contract(
            timeout_seconds=10,
            interval_seconds=0,
            monotonic=lambda: next(clock),
            sleep=lambda _s: None,
        )
    assert failure.value.reason == "flow_run_table_missing"
