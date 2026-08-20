"""Prove the materialized balances still agree with the movement ledger.

Materializing stock moved the read path off the ledger. This re-derives every
balance from the ledger and reports any disagreement, which is the evidence that
computed stock is preserved (`spec.md` §8.4).

Read-only: it never writes, so it is safe to run against production at any time.
Exits non-zero when any row drifts, so it can gate a release.

Usage:
    python -m scripts.verify_stock_balances
"""

from __future__ import annotations

import logging
import sys

from sqlmodel import Session

from central_api.db.session import get_engine
from central_api.domains.inventory.balances import verify_stock_balances

logger = logging.getLogger("central_api.verify_stock_balances")

# A drifting row names a SKU and a quantity, which are business data. Log counts
# and identifiers only, never the values, consistent with the other scripts here.
MAX_REPORTED = 20


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    with Session(get_engine()) as session:
        drifted = verify_stock_balances(session)
    if not drifted:
        logger.info("stock_balances=verified drift_rows=0")
        return
    logger.error("stock_balances=drifted drift_rows=%s", len(drifted))
    for row in drifted[:MAX_REPORTED]:
        logger.error(
            "stock_balance_drift sku_id=%s warehouse=%s delta=%s",
            row.sku_id,
            row.warehouse,
            row.derived - row.stored,
        )
    sys.exit(1)


if __name__ == "__main__":
    main()
