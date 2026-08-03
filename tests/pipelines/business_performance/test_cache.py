"""Normative one-hour application-managed cache behavior."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from pipelines.business_performance.cache import (
    CACHE_TTL,
    EVALUATION_VERSION,
    CacheConfig,
    CacheConfigurationError,
    CacheParameters,
    S3CacheStore,
    cache_store_from_environment,
    prefect_result_storage_from_environment,
    transformation_cache_key,
    transform_with_cache,
)
from pipelines.business_performance.flows import assemble_weekly_rows_cached
from process.business_performance import WeeklyPerformanceRow

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
WEEK = date(2026, 7, 13)


class _Body:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self) -> bytes:
        return self.value


class FakeObjectStore:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.read_error = False
        self.write_error = False
        self.write_attempts = 0

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if self.read_error:
            raise OSError("emulated read failure")
        value = self.objects.get((Bucket, Key))
        if value is None:
            raise OSError("not found")
        return {"Body": _Body(value)}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> object:
        del ContentType
        self.write_attempts += 1
        if self.write_error:
            raise OSError("emulated write failure")
        self.objects[(Bucket, Key)] = Body
        return {}


def _store(client: FakeObjectStore) -> S3CacheStore:
    return S3CacheStore(
        CacheConfig("private-test", "http://127.0.0.1:1", "fake", "fake"),
        client=client,
    )


def _row(*, inbound: int = 10) -> WeeklyPerformanceRow:
    return WeeklyPerformanceRow(
        warehouse="los_angeles",
        client_id="11111111-1111-4111-8111-111111111111",
        week_start=WEEK,
        inbound_units_count=inbound,
        outbound_orders_count=2,
        stockout_events_count=1,
        discrepancy_events_count=0,
        discrepancy_rate=Decimal(0),
    )


def _parameters(**changes: object) -> CacheParameters:
    values: dict[str, object] = {
        "source_digest": "source-a",
        "pipeline_version": "pipeline-v1",
        "evaluation_version": EVALUATION_VERSION,
        "target_weeks": (WEEK,),
        "recompute_weeks": 3,
        "sku_pairs": (("LA", "11111111-1111-4111-8111-111111111111"),),
        "last_reset_at": None,
        "cache_nonce": None,
    }
    values.update(changes)
    return CacheParameters(**values)  # type: ignore[arg-type]


def test_unchanged_content_hits_cache_but_load_still_runs() -> None:
    client = FakeObjectStore()
    store = _store(client)
    computes = 0
    loads = 0

    def compute() -> list[WeeklyPerformanceRow]:
        nonlocal computes
        computes += 1
        return [_row()]

    for _ in range(2):
        result = transform_with_cache(store, _parameters(), compute, now=NOW)
        loads += len(result.rows)
    assert computes == 1
    assert loads == 2
    assert result.cache_hit is True


@pytest.mark.parametrize(
    "changes",
    [
        {"source_digest": "source-b"},
        {"pipeline_version": "pipeline-v2"},
        {"evaluation_version": "weekly-kpis-v2"},
        {"target_weeks": (date(2026, 7, 6),)},
        {"recompute_weeks": 4},
        {"sku_pairs": (("ZGZ", "11111111-1111-4111-8111-111111111111"),)},
        {"last_reset_at": datetime(2026, 7, 13, 0, 0, tzinfo=UTC)},
        {"cache_nonce": uuid4()},
    ],
)
def test_every_normative_parameter_changes_the_key(changes: dict[str, object]) -> None:
    assert transformation_cache_key(_parameters(**changes)) != transformation_cache_key(_parameters())


def test_count_preserving_source_edit_misses_via_content_digest() -> None:
    assert transformation_cache_key(_parameters(source_digest="quantity-10")) != transformation_cache_key(
        _parameters(source_digest="quantity-11")
    )


def test_expired_value_recomputes() -> None:
    client = FakeObjectStore()
    store = _store(client)
    first = transform_with_cache(store, _parameters(), lambda: [_row()], now=NOW)
    second = transform_with_cache(
        store,
        _parameters(),
        lambda: [_row(inbound=20)],
        now=NOW + CACHE_TTL,
    )
    assert first.cache_hit is False
    assert second.cache_hit is False
    assert second.rows[0].inbound_units_count == 20


def test_absent_cache_config_computes_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "REPORTING_R2_BUCKET",
        "REPORTING_R2_ENDPOINT",
        "REPORTING_R2_ACCESS_KEY_ID",
        "REPORTING_R2_SECRET_ACCESS_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    assert cache_store_from_environment() is None
    result = transform_with_cache(None, _parameters(), lambda: [_row()], now=NOW)
    assert result.cache_hit is False
    assert result.rows == [_row()]
    assert prefect_result_storage_from_environment() is None


def test_prefect_recovery_storage_uses_a_distinct_private_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORTING_R2_BUCKET", "private-reporting")
    monkeypatch.setenv("REPORTING_R2_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("REPORTING_R2_ACCESS_KEY_ID", "scoped-id")
    monkeypatch.setenv("REPORTING_R2_SECRET_ACCESS_KEY", "scoped-secret")
    storage = prefect_result_storage_from_environment()
    assert storage is not None
    assert storage.bucket_name == "private-reporting"
    assert storage.bucket_folder == "prefect-results/recovery"


def test_partial_cache_config_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORTING_R2_BUCKET", "private")
    with pytest.raises(CacheConfigurationError, match="complete or absent"):
        CacheConfig.from_environment()


def test_read_and_write_failures_degrade_to_recomputation() -> None:
    client = FakeObjectStore()
    client.read_error = True
    client.write_error = True
    store = _store(client)
    sleeps: list[float] = []
    assert store.read("missing", now=NOW) is None
    assert store.write("missing", [_row()], now=NOW, sleeper=sleeps.append) is False
    assert client.write_attempts == 3
    assert sleeps == [0.1, 0.2]
    result = transform_with_cache(store, _parameters(), lambda: [_row()], now=NOW)
    assert result.cache_hit is False


def test_prefect_task_retains_required_cache_metadata() -> None:
    assert assemble_weekly_rows_cached.cache_key_fn is not None
    assert assemble_weekly_rows_cached.cache_expiration == CACHE_TTL
