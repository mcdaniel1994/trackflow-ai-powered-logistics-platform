"""Application-managed, disposable S3-compatible cache for pure KPI rows."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final, Protocol, cast
from uuid import UUID

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from process.business_performance import WeeklyPerformanceRow

CACHE_PREFIX: Final = "prefect-results/"
CACHE_TTL: Final = timedelta(hours=1)
EVALUATION_VERSION: Final = "weekly-kpis-v1"
logger = logging.getLogger(__name__)


class CacheConfigurationError(RuntimeError):
    """Raised when only part of the private cache configuration is present."""


class ObjectStore(Protocol):
    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]: ...

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> object: ...


@dataclass(frozen=True)
class CacheConfig:
    bucket: str
    endpoint: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    region: str = "auto"
    prefix: str = CACHE_PREFIX

    @classmethod
    def from_environment(cls) -> CacheConfig | None:
        names = (
            "REPORTING_R2_BUCKET",
            "REPORTING_R2_ENDPOINT",
            "REPORTING_R2_ACCESS_KEY_ID",
            "REPORTING_R2_SECRET_ACCESS_KEY",
        )
        values = {name: os.environ.get(name, "").strip() for name in names}
        if not any(values.values()):
            return None
        if not all(values.values()):
            raise CacheConfigurationError("REPORTING_R2 configuration must be complete or absent")
        return cls(
            bucket=values["REPORTING_R2_BUCKET"],
            endpoint=values["REPORTING_R2_ENDPOINT"],
            access_key_id=values["REPORTING_R2_ACCESS_KEY_ID"],
            secret_access_key=values["REPORTING_R2_SECRET_ACCESS_KEY"],
        )


@dataclass(frozen=True)
class CacheParameters:
    source_digest: str
    pipeline_version: str
    evaluation_version: str
    target_weeks: tuple[date, ...]
    recompute_weeks: int
    sku_pairs: tuple[tuple[str, str], ...] = ()
    last_reset_at: datetime | None = None
    cache_nonce: UUID | None = None


@dataclass(frozen=True)
class CachedTransform:
    rows: list[WeeklyPerformanceRow]
    cache_hit: bool


def transformation_cache_key(parameters: CacheParameters) -> str:
    payload = {
        "source_content_digest": parameters.source_digest,
        "pipeline_version": parameters.pipeline_version,
        "evaluation_version": parameters.evaluation_version,
        "target_weeks": [week.isoformat() for week in parameters.target_weeks],
        "recompute_weeks": parameters.recompute_weeks,
        "sku_pairs": sorted(parameters.sku_pairs),
        "last_reset_at": (
            parameters.last_reset_at.astimezone(UTC).isoformat() if parameters.last_reset_at else None
        ),
        "cache_nonce": str(parameters.cache_nonce) if parameters.cache_nonce else None,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def prefect_transformation_cache_key(_context: object, parameters: dict[str, Any]) -> str:
    """Expose the approved key on the Prefect task even though storage is app-managed."""
    return transformation_cache_key(
        CacheParameters(
            source_digest=cast(str, parameters["source_digest"]),
            pipeline_version=cast(str, parameters["pipeline_version"]),
            evaluation_version=cast(str, parameters["evaluation_version"]),
            target_weeks=tuple(cast(Sequence[date], parameters["target_weeks"])),
            recompute_weeks=cast(int, parameters["recompute_weeks"]),
            sku_pairs=tuple(cast(Sequence[tuple[str, str]], parameters["sku_pairs"])),
            last_reset_at=cast(datetime | None, parameters["last_reset_at"]),
            cache_nonce=cast(UUID | None, parameters["cache_nonce"]),
        )
    )


def _encode_rows(rows: Sequence[WeeklyPerformanceRow], created_at: datetime) -> bytes:
    payload = {
        "created_at": created_at.astimezone(UTC).isoformat(),
        "rows": [
            {
                "warehouse": row.warehouse,
                "client_id": row.client_id,
                "week_start": row.week_start.isoformat(),
                "inbound_units_count": row.inbound_units_count,
                "outbound_orders_count": row.outbound_orders_count,
                "stockout_events_count": row.stockout_events_count,
                "discrepancy_events_count": row.discrepancy_events_count,
                "discrepancy_rate": str(row.discrepancy_rate),
            }
            for row in rows
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _decode_rows(payload: bytes) -> tuple[datetime, list[WeeklyPerformanceRow]]:
    decoded = cast(dict[str, Any], json.loads(payload))
    created_at = datetime.fromisoformat(cast(str, decoded["created_at"]))
    rows = [
        WeeklyPerformanceRow(
            warehouse=cast(str, item["warehouse"]),
            client_id=cast(str, item["client_id"]),
            week_start=date.fromisoformat(cast(str, item["week_start"])),
            inbound_units_count=cast(int, item["inbound_units_count"]),
            outbound_orders_count=cast(int, item["outbound_orders_count"]),
            stockout_events_count=cast(int, item["stockout_events_count"]),
            discrepancy_events_count=cast(int, item["discrepancy_events_count"]),
            discrepancy_rate=Decimal(cast(str, item["discrepancy_rate"])),
        )
        for item in cast(list[dict[str, Any]], decoded["rows"])
    ]
    return created_at, rows


class S3CacheStore:
    """Small direct-boto3 adapter selected by the no-Prefect-server spike."""

    def __init__(self, config: CacheConfig, *, client: ObjectStore | None = None) -> None:
        self.config = config
        self.client = client or boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region,
        )

    def object_key(self, cache_key: str) -> str:
        return f"{self.config.prefix}{cache_key}.json"

    def read(
        self,
        cache_key: str,
        *,
        now: datetime,
        ttl: timedelta = CACHE_TTL,
    ) -> list[WeeklyPerformanceRow] | None:
        try:
            response = self.client.get_object(Bucket=self.config.bucket, Key=self.object_key(cache_key))
            body = cast(Any, response["Body"]).read()
            created_at, rows = _decode_rows(cast(bytes, body))
        except (BotoCoreError, ClientError, OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if now.astimezone(UTC) - created_at.astimezone(UTC) >= ttl:
            return None
        return rows

    def write(
        self,
        cache_key: str,
        rows: Sequence[WeeklyPerformanceRow],
        *,
        now: datetime,
        retry_delays: tuple[float, ...] = (0.1, 0.2),
        sleeper: Callable[[float], None] = time.sleep,
    ) -> bool:
        body = _encode_rows(rows, now)
        for attempt in range(len(retry_delays) + 1):
            try:
                self.client.put_object(
                    Bucket=self.config.bucket,
                    Key=self.object_key(cache_key),
                    Body=body,
                    ContentType="application/json",
                )
                return True
            except (BotoCoreError, ClientError, OSError):
                if attempt == len(retry_delays):
                    logger.warning("reporting_cache_write_skipped reason=storage_unavailable")
                    return False
                sleeper(retry_delays[attempt])
        return False


def cache_store_from_environment() -> S3CacheStore | None:
    config = CacheConfig.from_environment()
    return None if config is None else S3CacheStore(config)


def transform_with_cache(
    store: S3CacheStore | None,
    parameters: CacheParameters,
    compute: Callable[[], list[WeeklyPerformanceRow]],
    *,
    now: datetime | None = None,
) -> CachedTransform:
    current_time = now or datetime.now(UTC)
    key = transformation_cache_key(parameters)
    if store is not None:
        cached = store.read(key, now=current_time)
        if cached is not None:
            return CachedTransform(cached, cache_hit=True)
    rows = compute()
    if store is not None:
        store.write(key, rows, now=current_time)
    return CachedTransform(rows, cache_hit=False)
