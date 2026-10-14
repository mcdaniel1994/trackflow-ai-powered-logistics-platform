"""Public indexing pins source and target; no provider calls are made here."""

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from central_api.core.config import Settings
from scripts import rag_index


def test_public_index_pins_curated_folder_and_separate_collection(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    monkeypatch.setattr(sys, "argv", ["rag-index", "--public"])
    monkeypatch.setattr(rag_index, "get_settings", lambda: settings.model_copy(update={"openai_api_key": "fake"}))
    calls: dict[str, Any] = {}

    def setup(config: Any, **kwargs: Any) -> Any:
        calls.update(config=config, **kwargs)
        return SimpleNamespace(collection=config.collection, documents=3, chunks=10)

    monkeypatch.setattr(rag_index, "setup", setup)
    rag_index.entrypoint()
    assert calls["config"].collection == "trackflow_public"
    assert calls["corpus_dir"] == Path(__file__).resolve().parents[3] / "docs" / "public-knowledge-base"
    assert calls["recreate"] is False


@pytest.mark.parametrize("arguments", [["--recreate"], ["--corpus-dir", "private"]])
def test_public_index_rejects_custom_or_destructive_inputs(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["rag-index", "--public", *arguments])
    monkeypatch.setattr(rag_index, "setup", lambda *_a, **_k: pytest.fail("Must not reach providers"))
    with pytest.raises(SystemExit) as error:
        rag_index.entrypoint()
    assert error.value.code == 2
