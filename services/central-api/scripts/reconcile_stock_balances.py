"""Detect and correct drift between the materialized balances and the ledger.

The incremental path in ``InventoryService`` cannot drift under concurrency, but
a deployment can: the database migrates first, then containers are swapped, and
until the swap finishes the previous image keeps writing movements without
maintaining ``stock_balances``. Those writes are usually net outbound, which
leaves the stored balance *higher* than the ledger -- so the API will approve
dispatches the ledger cannot cover until the balance is corrected.

The maintenance worker runs this at startup and on every 15-minute guard tick, so
rollover drift is corrected automatically. It is also safe to run by hand.

Corrections are logged at ERROR with the per-SKU delta. Drift is never expected
in steady state, so a silent repair would hide a genuine bug in the incremental
path; the log is what distinguishes routine rollover from a real defect.

Usage:
    python -m scripts.reconcile_stock_balances
"""

from __future__ import annotations

import logging

from sqlmodel import Session

from central_api.db.session import get_engine
from central_api.domains.inventory.balances import reconcile_stock_balances

logger = logging.getLogger("central_api.reconcile_stock_balances")

# Deltas name a SKU and a quantity, which are business data. Bound the volume and
# log identifiers plus the correction only, consistent with the other scripts.
MAX_REPORTED = 20


def reconcile_once() -> int:
    """Correct any drift and return how many rows were corrected."""
    with Session(get_engine()) as session:
        corrected = reconcile_stock_balances(session)
        session.commit()
    if not corrected:
        logger.info("stock_balances=reconciled drift_rows=0")
        return 0
    logger.error("stock_balances=corrected drift_rows=%s", len(corrected))
    for row in corrected[:MAX_REPORTED]:
        logger.error(
            "stock_balance_corrected sku_id=%s warehouse=%s delta=%s",
            row.sku_id,
            row.warehouse,
            row.delta,
        )
    return len(corrected)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    reconcile_once()


if __name__ == "__main__":
    main()
