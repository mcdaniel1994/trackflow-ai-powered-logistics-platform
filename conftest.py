"""Keep per-service pytest commands scoped when run from the monorepo root."""

from __future__ import annotations

import importlib.util

collect_ignore_glob: list[str] = []

has_incident_processor = importlib.util.find_spec("incident_processor") is not None
has_supplier_directory = importlib.util.find_spec("supplier_directory") is not None

if has_supplier_directory and not has_incident_processor:
    collect_ignore_glob.append("services/incident-processor/tests/*")

if has_incident_processor and not has_supplier_directory:
    collect_ignore_glob.append("services/supplier-directory/tests/*")
