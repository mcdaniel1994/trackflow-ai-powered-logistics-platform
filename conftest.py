"""Keep per-service pytest commands scoped when run from the monorepo root."""

from __future__ import annotations

import importlib.util

collect_ignore_glob: list[str] = []
collect_ignore: list[str] = []


def ignore_tests(path: str) -> None:
    collect_ignore.append(path)
    collect_ignore_glob.append(f"{path}/*")

has_incident_processor = importlib.util.find_spec("incident_processor") is not None
has_supplier_directory = importlib.util.find_spec("supplier_directory") is not None
has_identity = importlib.util.find_spec("identity") is not None

if has_supplier_directory and not has_incident_processor:
    ignore_tests("services/incident-processor/tests")

if has_supplier_directory and not has_identity:
    ignore_tests("services/identity/tests")

if has_incident_processor and not has_supplier_directory:
    ignore_tests("services/supplier-directory/tests")

if has_incident_processor and not has_identity:
    ignore_tests("services/identity/tests")

if has_identity and not has_incident_processor:
    ignore_tests("services/incident-processor/tests")

if has_identity and not has_supplier_directory:
    ignore_tests("services/supplier-directory/tests")
