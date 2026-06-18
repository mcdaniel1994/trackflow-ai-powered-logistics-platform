from __future__ import annotations

from supplier_directory.repository import SupplierRepository
from supplier_directory.seed import SUPPLIERS_SEED
from supplier_directory.service import SupplierService


def test_seed_inserts_expected_count_and_is_idempotent(tmp_path):
    repository = SupplierRepository(tmp_path / "suppliers.json")
    service = SupplierService(repository)

    try:
        assert service.seed_suppliers(SUPPLIERS_SEED) == 15
        assert repository.count() == 15
        assert service.seed_suppliers(SUPPLIERS_SEED) == 0
        assert repository.count() == 15
    finally:
        repository.close()
