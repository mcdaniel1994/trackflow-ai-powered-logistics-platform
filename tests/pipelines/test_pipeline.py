"""In-memory correctness tests for the pure business-performance transform."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pipelines

from process.business_performance import (
    TransformError,
    assemble_weekly_rows,
    compute_discrepancy_rate,
    compute_inbound_volume,
    compute_outbound_throughput,
    compute_stockout_frequency,
    iso_week_start,
    recomputable_weeks,
    reset_incomplete_weeks,
    source_content_digest,
    validate_requested_week,
    week_is_incomplete,
)

CLIENT_A = "11111111-1111-4111-8111-111111111111"
CLIENT_B = "22222222-2222-4222-8222-222222222222"
WEEK = date(2026, 7, 13)


def _empty_activity() -> dict[str, list[dict[str, object]]]:
    return {
        "inbound_order_created": [],
        "outbound_order_created": [],
        "stock_threshold_triggered": [],
        "inventory_discrepancy_detected": [],
    }


def _event(
    event_id: int,
    *,
    warehouse: str = "LA",
    client_id: str = CLIENT_A,
    occurred_at: datetime = datetime(2026, 7, 14, 12, tzinfo=UTC),
    quantity: int | None = None,
    quantity_delta: int | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "id": event_id,
        "occurred_at": occurred_at,
        "warehouse": warehouse,
        "client_id": client_id,
    }
    if quantity is not None:
        record["quantity"] = quantity
    if quantity_delta is not None:
        record["quantity_delta"] = quantity_delta
    return record


def _fixture_activity() -> dict[str, list[dict[str, object]]]:
    activity = _empty_activity()
    activity["inbound_order_created"] = [
        _event(2, quantity=5),
        _event(1, quantity=10),
        _event(3, warehouse="ZGZ", client_id=CLIENT_B, quantity=7),
    ]
    activity["outbound_order_created"] = [
        _event(11, quantity=3),
        _event(12, quantity=2),
        _event(13, warehouse="ZGZ", client_id=CLIENT_B, quantity=1),
    ]
    activity["stock_threshold_triggered"] = [_event(21)]
    activity["inventory_discrepancy_detected"] = [_event(31, quantity_delta=-1)]
    return activity


def test_hand_calculated_kpis_and_dimension_isolation() -> None:
    rows = assemble_weekly_rows(
        _fixture_activity(),
        sku_pairs=(("LA", CLIENT_A), ("ZGZ", CLIENT_B)),
        target_weeks=(WEEK,),
    )
    assert [row.business_values() for row in rows] == [
        {
            "warehouse": "los_angeles",
            "client_id": CLIENT_A,
            "week_start": WEEK,
            "inbound_units_count": 15,
            "outbound_orders_count": 2,
            "stockout_events_count": 1,
            "discrepancy_events_count": 1,
            "discrepancy_rate": Decimal("0.5"),
        },
        {
            "warehouse": "zaragoza",
            "client_id": CLIENT_B,
            "week_start": WEEK,
            "inbound_units_count": 7,
            "outbound_orders_count": 1,
            "stockout_events_count": 0,
            "discrepancy_events_count": 0,
            "discrepancy_rate": Decimal(0),
        },
    ]


@pytest.mark.parametrize(
    ("source", "record"),
    [
        ("inbound_order_created", _event(1)),
        ("inbound_order_created", {**_event(1, quantity=1), "quantity": "1"}),
        ("inbound_order_created", {**_event(1, quantity=1), "warehouse": "NYC"}),
    ],
)
def test_bad_source_record_fails_without_partial_output(source: str, record: dict[str, object]) -> None:
    activity = _empty_activity()
    activity[source] = [record]
    with pytest.raises(TransformError):
        assemble_weekly_rows(activity, sku_pairs=(("LA", CLIENT_A),), target_weeks=(WEEK,))


def test_iso_week_uses_utc_boundary_and_rejects_naive_timestamps() -> None:
    assert iso_week_start(datetime(2026, 7, 12, 23, 59, 59, tzinfo=UTC)) == date(2026, 7, 6)
    assert iso_week_start(datetime(2026, 7, 13, 0, 0, tzinfo=UTC)) == WEEK
    assert iso_week_start(datetime(2026, 7, 12, 20, 0, tzinfo=timezone(timedelta(hours=-4)))) == WEEK
    with pytest.raises(TransformError):
        iso_week_start(datetime(2026, 7, 13, 0, 0))


def test_standalone_kpi_functions_deduplicate_and_zero_rate_is_exact() -> None:
    inbound = [_event(1, quantity=5), _event(1, quantity=5)]
    outbound = [_event(2, quantity=1), _event(2, quantity=1)]
    stockout = [_event(3), _event(3)]
    assert compute_inbound_volume(inbound) == 5
    assert compute_outbound_throughput(outbound) == 1
    assert compute_stockout_frequency(stockout) == 1
    assert compute_discrepancy_rate(0, 0) == Decimal(0)


def test_conflicting_duplicate_and_impossible_discrepancy_rate_are_rejected() -> None:
    activity = _empty_activity()
    activity["inbound_order_created"] = [_event(1, quantity=2), _event(1, quantity=3)]
    with pytest.raises(TransformError, match="conflicting duplicate"):
        assemble_weekly_rows(activity, sku_pairs=(("LA", CLIENT_A),), target_weeks=(WEEK,))
    with pytest.raises(TransformError, match="cannot exceed"):
        compute_discrepancy_rate(2, 1)


def test_late_arrival_changes_only_a_recomputed_target_week() -> None:
    activity = _empty_activity()
    activity["inbound_order_created"] = [_event(1, quantity=5)]
    original = assemble_weekly_rows(activity, sku_pairs=(("LA", CLIENT_A),), target_weeks=(WEEK,))

    inside = deepcopy(activity)
    inside["inbound_order_created"].append(_event(2, quantity=4))
    assert assemble_weekly_rows(inside, sku_pairs=(("LA", CLIENT_A),), target_weeks=(WEEK,)) != original

    outside = deepcopy(activity)
    outside["inbound_order_created"].append(
        _event(3, occurred_at=datetime(2026, 7, 7, 12, tzinfo=UTC), quantity=9)
    )
    assert assemble_weekly_rows(outside, sku_pairs=(("LA", CLIENT_A),), target_weeks=(WEEK,)) == original


def test_rerun_is_idempotent_and_sku_pairs_receive_explicit_zero_rows() -> None:
    activity = _empty_activity()
    first = assemble_weekly_rows(
        activity,
        sku_pairs=(("LA", CLIENT_A), ("ZGZ", CLIENT_B)),
        target_weeks=(WEEK,),
    )
    second = assemble_weekly_rows(
        deepcopy(activity),
        sku_pairs=(("ZGZ", CLIENT_B), ("LA", CLIENT_A)),
        target_weeks=(WEEK,),
    )
    assert first == second
    assert len(first) == 2
    assert all(row.inbound_units_count == row.outbound_orders_count == 0 for row in first)


def test_content_digest_is_order_stable_and_detects_count_preserving_changes() -> None:
    activity = _fixture_activity()
    reordered = deepcopy(activity)
    reordered["inbound_order_created"].reverse()
    assert source_content_digest(activity) == source_content_digest(reordered)

    changed = deepcopy(activity)
    changed["inbound_order_created"][0]["quantity"] = 6
    assert source_content_digest(activity) != source_content_digest(changed)


def test_reset_boundary_freezes_partial_week_for_upsert_and_stale_delete_sets() -> None:
    weeks = (date(2026, 7, 6), WEEK, date(2026, 7, 20))
    reset_at = datetime(2026, 7, 14, 12, tzinfo=UTC)
    assert recomputable_weeks(weeks, reset_at) == (date(2026, 7, 20),)

    before = assemble_weekly_rows(
        _fixture_activity(),
        sku_pairs=(("LA", CLIENT_A), ("ZGZ", CLIENT_B)),
        target_weeks=(WEEK,),
    )
    assert before
    after = assemble_weekly_rows(
        _empty_activity(),
        sku_pairs=(("LA", CLIENT_A),),
        target_weeks=(WEEK, date(2026, 7, 20)),
        last_reset_at=reset_at,
    )
    assert [row.week_start for row in after] == [date(2026, 7, 20)]
    assert reset_incomplete_weeks(reset_at, weeks, checkpoint_succeeded=True) == {WEEK: "ledger_reset"}


def test_frozen_manual_week_checkpoint_failure_and_incomplete_flag() -> None:
    weeks = (date(2026, 7, 6), WEEK, date(2026, 7, 20))
    reset_at = datetime(2026, 7, 14, 12, tzinfo=UTC)
    with pytest.raises(TransformError, match="precedes last ledger reset"):
        validate_requested_week(WEEK, reset_at)
    assert validate_requested_week(date(2026, 7, 20), reset_at) == date(2026, 7, 20)

    incomplete = reset_incomplete_weeks(reset_at, weeks, checkpoint_succeeded=False)
    assert incomplete == {week: "reset_checkpoint_failed" for week in weeks}
    assert week_is_incomplete(WEEK, incomplete) is True
    assert week_is_incomplete(date(2026, 7, 27), incomplete) is False


def test_package_and_remaining_boundary_validation() -> None:
    assert pipelines.__doc__

    missing_source = _empty_activity()
    del missing_source["stock_threshold_triggered"]
    with pytest.raises(TransformError, match="exactly the four"):
        source_content_digest(missing_source)

    invalid_records: list[object] = ["not-a-record-list", ["not-a-mapping"]]
    for records in invalid_records:
        with pytest.raises(TransformError):
            compute_inbound_volume(records)  # type: ignore[arg-type]

    invalid_discrepancy = _empty_activity()
    invalid_discrepancy["inventory_discrepancy_detected"] = [_event(1, quantity_delta=0)]
    with pytest.raises(TransformError, match="non-zero"):
        source_content_digest(invalid_discrepancy)

    invalid_client = _empty_activity()
    invalid_client["inbound_order_created"] = [_event(1, client_id="not-a-uuid", quantity=1)]
    with pytest.raises(TransformError, match="UUID"):
        source_content_digest(invalid_client)

    for counts in ((-1, 1), (True, 1)):
        with pytest.raises(TransformError, match="non-negative"):
            compute_discrepancy_rate(*counts)

    with pytest.raises(TransformError, match="date values"):
        recomputable_weeks((datetime(2026, 7, 13, tzinfo=UTC),), None)  # type: ignore[arg-type]
    with pytest.raises(TransformError, match="Monday"):
        recomputable_weeks((date(2026, 7, 14),), None)
    with pytest.raises(TransformError, match="pairs"):
        assemble_weekly_rows(_empty_activity(), sku_pairs=(["LA", CLIENT_A],), target_weeks=(WEEK,))  # type: ignore[arg-type]

    orphan_activity = _empty_activity()
    orphan_activity["inbound_order_created"] = [_event(1, quantity=1)]
    with pytest.raises(TransformError, match="without a SKU"):
        assemble_weekly_rows(orphan_activity, sku_pairs=(("ZGZ", CLIENT_B),), target_weeks=(WEEK,))
