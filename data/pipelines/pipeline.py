"""Direct one-shot CLI for the weekly business-performance pipeline."""

from __future__ import annotations

import argparse
from datetime import date

from pipelines.business_performance.flows import prefect_executor
from pipelines.business_performance.queue import engine_from_environment, enqueue_cli
from pipelines.business_performance.runner import RunnerStatus, run_once


def _week_start(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoweekday() != 1:
        raise argparse.ArgumentTypeError("--week-start must be an ISO Monday")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-start", type=_week_start)
    args = parser.parse_args()
    engine = engine_from_environment()
    try:
        enqueue_cli(engine, requested_week_start=args.week_start)
        result = run_once(engine, prefect_executor)
    finally:
        engine.dispose()
    return 0 if result.status == RunnerStatus.SUCCEEDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
