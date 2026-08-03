"""Graded root path (Engagement 7 instructions): ``python -m pytest tests/pipelines/test_rag.py``.

The real tests were reorganised into ``tests/pipelines/rag/test_rag.py`` (Engagement 8 Phase 0 folder
categorisation). This shim re-exports them so the graded evaluator command still collects and runs the
suite. The full/CI run targets the category subfolders directly, so this shim is only collected when
named explicitly and never double-collected.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REAL = Path(__file__).parent / "rag" / "test_rag.py"
_spec = importlib.util.spec_from_file_location("rag.test_rag", _REAL)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

globals().update({_name: _value for _name, _value in vars(_module).items() if not _name.startswith("__")})
