"""Milestone-required root path (PIPELINE_DESIGN.md §M6): ``tests/pipelines/test_pipeline.py``.

The real tests were reorganised into ``tests/pipelines/business_performance/test_pipeline.py``
(Engagement 8 Phase 0 folder categorisation). This shim re-exports them so the evaluator command
``python -m pytest tests/pipelines/test_pipeline.py`` still collects and runs the full suite.

The full/CI run targets the category subfolders directly (see ``data/pyproject.toml`` ``testpaths``
and ``.github/workflows/release-checks.yml``), so this shim is only collected when named explicitly
— it is never double-collected alongside the real module.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REAL = Path(__file__).parent / "business_performance" / "test_pipeline.py"
_spec = importlib.util.spec_from_file_location("business_performance.test_pipeline", _REAL)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

# Re-export every public name (test functions AND fixtures) into this module's namespace so pytest
# collects them under the milestone root path.
globals().update({_name: _value for _name, _value in vars(_module).items() if not _name.startswith("__")})
