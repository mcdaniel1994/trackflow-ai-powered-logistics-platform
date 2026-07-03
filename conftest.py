"""Keep per-service pytest commands scoped when run from the monorepo root."""

from __future__ import annotations

import importlib.util

collect_ignore_glob: list[str] = []
collect_ignore: list[str] = []


def ignore_tests(path: str) -> None:
    collect_ignore.append(path)
    collect_ignore_glob.append(f"{path}/*")

has_supplier_directory = importlib.util.find_spec("supplier_directory") is not None
has_identity = importlib.util.find_spec("identity") is not None
has_central_api = importlib.util.find_spec("central_api") is not None

if has_central_api:
    ignore_tests("services/identity/tests")
    ignore_tests("services/supplier-directory/tests")

if has_supplier_directory and not has_identity and not has_central_api:
    ignore_tests("services/identity/tests")
    ignore_tests("services/central-api/tests")
    ignore_tests("packages/trackflow_incidents/tests")

if has_identity and not has_supplier_directory and not has_central_api:
    ignore_tests("services/supplier-directory/tests")
    ignore_tests("services/central-api/tests")
    ignore_tests("packages/trackflow_incidents/tests")
