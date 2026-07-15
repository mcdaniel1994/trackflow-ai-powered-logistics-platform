"""Prove application-managed S3 cache reuse across two fresh processes."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import UTC, date, datetime
from decimal import Decimal

import boto3  # type: ignore[import-untyped]

from pipelines.business_performance.cache import (
    EVALUATION_VERSION,
    CacheParameters,
    cache_store_from_environment,
    transform_with_cache,
)
from process.business_performance import WeeklyPerformanceRow


def _sample_row() -> WeeklyPerformanceRow:
    return WeeklyPerformanceRow(
        warehouse="los_angeles",
        client_id="11111111-1111-4111-8111-111111111111",
        week_start=date(2026, 7, 13),
        inbound_units_count=10,
        outbound_orders_count=2,
        stockout_events_count=1,
        discrepancy_events_count=0,
        discrepancy_rate=Decimal(0),
    )


def worker() -> int:
    store = cache_store_from_environment()
    if store is None:
        raise RuntimeError("spike worker requires emulated R2 configuration")
    computed = False

    def compute() -> list[WeeklyPerformanceRow]:
        nonlocal computed
        computed = True
        return [_sample_row()]

    result = transform_with_cache(
        store,
        CacheParameters(
            source_digest="spike-source-digest",
            pipeline_version="spike-v1",
            evaluation_version=EVALUATION_VERSION,
            target_weeks=(date(2026, 7, 13),),
            recompute_weeks=3,
            sku_pairs=(("LA", "11111111-1111-4111-8111-111111111111"),),
        ),
        compute,
        now=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
    )
    print(json.dumps({"cache_hit": result.cache_hit, "computed": computed, "row_count": len(result.rows)}))
    return 0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_spike() -> int:
    from moto.server import ThreadedMotoServer

    port = _free_port()
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port, verbose=False)
    server.start()
    endpoint = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update(
        {
            "REPORTING_R2_BUCKET": "trackflow-spike-private",
            "REPORTING_R2_ENDPOINT": endpoint,
            "REPORTING_R2_ACCESS_KEY_ID": "spike-only",
            "REPORTING_R2_SECRET_ACCESS_KEY": "spike-only",
            "PREFECT_API_URL": "",
        }
    )
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id="spike-only",
            aws_secret_access_key="spike-only",
            region_name="us-east-1",
        )
        client.create_bucket(Bucket="trackflow-spike-private")
        command = [sys.executable, str(__file__), "--worker"]
        first = json.loads(subprocess.run(command, env=environment, check=True, capture_output=True, text=True).stdout)
        second = json.loads(subprocess.run(command, env=environment, check=True, capture_output=True, text=True).stdout)
        if first != {"cache_hit": False, "computed": True, "row_count": 1}:
            raise RuntimeError(f"unexpected first-process result: {first}")
        if second != {"cache_hit": True, "computed": False, "row_count": 1}:
            raise RuntimeError(f"cross-process cache reuse failed: {second}")
        print(json.dumps({"mechanism": "application-managed-boto3", "first": first, "second": second}))
        return 0
    finally:
        server.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    return worker() if args.worker else run_spike()


if __name__ == "__main__":
    raise SystemExit(main())
