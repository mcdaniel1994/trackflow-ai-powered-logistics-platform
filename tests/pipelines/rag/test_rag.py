"""Unit tests for the RAG retrieval + generation pipeline (Engagement 7).

No live Qdrant, OpenAI, or DeepSeek is required. ``retrieve`` is tested against a stubbed
Qdrant client; ``query`` is tested with ``retrieve`` and the generation client both mocked.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from pipelines import rag
from process.rag import Chunk, chunk_document, source_document_slug


def _config() -> rag.RagConfig:
    return rag.RagConfig(
        qdrant_url="http://qdrant.test:6333",
        qdrant_api_key=None,
        collection="trackflow",
        openai_api_key="test-openai",
        embedding_model="text-embedding-3-small",
        embedding_dim=8,
        deepseek_api_key="test-deepseek",
        deepseek_base_url="https://api.deepseek.test",
        generation_model="deepseek-chat",
        top_k=3,
        min_score=0.5,
    )


class _StubQdrant:
    """Returns preset points and records the query it was asked to run."""

    def __init__(self, points: list[SimpleNamespace]) -> None:
        self._points = points
        self.calls: list[dict[str, Any]] = []

    def query_points(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(points=self._points)


def _point(
    score: float, source: str, text: str, jurisdiction: str = "GLOBAL"
) -> SimpleNamespace:
    return SimpleNamespace(
        score=score,
        payload={
            "source_document": source,
            "section": source,
            "text": text,
            "jurisdiction": jurisdiction,
        },
    )


# --------------------------------------------------------------------------- retrieve()


def test_retrieve_excludes_hits_below_min_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    points = [
        _point(0.91, "returns-policy", "30 day window"),
        _point(0.40, "storage-pricing", "irrelevant"),  # below threshold 0.5 -> dropped
        _point(0.66, "sla-delivery", "standard 3-5 days"),
    ]
    stub = _StubQdrant(points)
    monkeypatch.setattr(rag, "_qdrant", lambda *_a, **_k: stub)
    monkeypatch.setattr(rag, "embed", lambda *_a, **_k: [0.0] * 8)

    results = rag.retrieve("standard return window?", config=_config())

    assert len(results) == 2  # the 0.40 hit was filtered out
    assert all(isinstance(row, dict) for row in results)  # payloads, not SDK objects
    assert {row["source_document"] for row in results} == {
        "returns-policy",
        "sla-delivery",
    }


def test_retrieve_can_return_fewer_than_k_or_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _StubQdrant(
        [_point(0.10, "storage-pricing", "weak"), _point(0.20, "sla-delivery", "weak")]
    )
    monkeypatch.setattr(rag, "_qdrant", lambda *_a, **_k: stub)
    monkeypatch.setattr(rag, "embed", lambda *_a, **_k: [0.0] * 8)

    results = rag.retrieve("something unrelated", config=_config())

    assert results == []  # nothing cleared the bar; top-k did not force results
    assert stub.calls[0]["limit"] == 3  # k came from config


def test_retrieve_honours_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubQdrant([_point(0.55, "sla-delivery", "text")])
    monkeypatch.setattr(rag, "_qdrant", lambda *_a, **_k: stub)
    monkeypatch.setattr(rag, "embed", lambda *_a, **_k: [0.0] * 8)

    results = rag.retrieve("q", k=1, min_score=0.9, config=_config())

    assert results == []  # 0.55 < explicit 0.9
    assert stub.calls[0]["limit"] == 1  # explicit k overrode config


def test_retrieve_filters_cross_jurisdiction_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _StubQdrant(
        [
            _point(0.9, "coverage", "UPS coverage", "US"),
            _point(0.9, "coverage", "SEUR coverage", "ES"),
            _point(0.9, "returns", "30 day return window", "GLOBAL"),
            SimpleNamespace(score=0.9, payload={"text": "legacy unlabelled passage"}),
        ]
    )
    monkeypatch.setattr(rag, "_qdrant", lambda *_a, **_k: stub)
    monkeypatch.setattr(rag, "embed", lambda *_a, **_k: [0.0] * 8)

    results = rag.retrieve("coverage", jurisdiction="US", config=_config())

    assert {row["jurisdiction"] for row in results} == {"US", "GLOBAL"}
    assert all("SEUR" not in str(row) for row in results)
    assert stub.calls[0]["query_filter"] is not None


def test_retrieve_wraps_vector_store_failure_as_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raw Qdrant/httpx failure (e.g. connection refused) becomes a RagPipelineError."""

    class _BrokenQdrant:
        def query_points(self, **_kwargs: Any) -> SimpleNamespace:
            raise ConnectionError("[Errno 61] Connection refused")

    monkeypatch.setattr(rag, "_qdrant", lambda *_a, **_k: _BrokenQdrant())
    monkeypatch.setattr(rag, "embed", lambda *_a, **_k: [0.0] * 8)

    with pytest.raises(rag.RagPipelineError):
        rag.retrieve("anything", config=_config())


# --------------------------------------------------------------------------- query()


class _StubChat:
    """Fake OpenAI-compatible chat client capturing the messages it is sent."""

    def __init__(self, answer: str, usage: object = None) -> None:
        self.answer = answer
        self.usage = usage
        self.received: dict[str, Any] = {}
        create = self._create
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.received = kwargs
        message = SimpleNamespace(content=self.answer)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=self.usage)


class _StubStream:
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.closed = False

    def __iter__(self):  # type: ignore[no-untyped-def]
        for content in self.chunks:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
                usage=None,
            )
        yield SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4, total_tokens=14),
        )

    def close(self) -> None:
        self.closed = True


class _StubStreamingChat:
    def __init__(self, chunks: list[str]) -> None:
        self.stream = _StubStream(chunks)
        self.received: dict[str, Any] = {}
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> _StubStream:
        self.received = kwargs
        return self.stream


def test_query_returns_generated_answer_not_raw_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_text = "Standard return window: 30 days from delivery."
    monkeypatch.setattr(
        rag,
        "retrieve",
        lambda *_a, **_k: [
            {
                "source_document": "returns-policy",
                "section": "Return window",
                "text": chunk_text,
            }
        ],
    )
    stub = _StubChat("Our standard return window is 30 days from delivery.")
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)

    answer = rag.query("what's the standard return window?", _config())

    assert answer == "Our standard return window is 30 days from delivery."
    assert answer != chunk_text  # the raw chunk was never returned directly
    # Context injection: the retrieved chunk text reached the generation model.
    user_message = stub.received["messages"][-1]["content"]
    assert chunk_text in user_message
    assert stub.received["model"] == "deepseek-chat"


def test_query_handles_empty_retrieval_honestly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rag, "retrieve", lambda *_a, **_k: [])
    stub = _StubChat("I don't have that documented, but I can follow up for you.")
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)

    answer = rag.query("do you accept crypto payments?", _config())

    assert answer  # still a model-generated answer
    user_message = stub.received["messages"][-1]["content"]
    assert "No relevant context" in user_message  # model told there was no context


def test_query_wraps_generation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag, "retrieve", lambda *_a, **_k: [])

    class _Boom:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._raise))

        def _raise(self, **_kwargs: Any) -> None:
            raise RuntimeError("provider down")

    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: _Boom())

    with pytest.raises(rag.RagPipelineError):
        rag.query("anything", _config())


def test_query_rejects_empty_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rag, "retrieve", lambda *_a, **_k: [])
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: _StubChat("   "))

    with pytest.raises(rag.RagPipelineError):
        rag.query("anything", _config())


def test_structured_generation_returns_answer_and_candidate_in_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = {
        "carrier_id": "11111111-1111-4111-8111-111111111111",
        "jurisdiction": "US",
        "kind": "recurring_operational_pattern",
        "subject_key": "late_scan_pattern",
        "fact": "Late scans recur during Tuesday handoffs.",
        "recurrence_count": 3,
        "effective_at": None,
    }
    stub = _StubChat(
        json.dumps(
            {
                "answer": "The repeated pattern is documented.",
                "memory_candidate": candidate,
            }
        )
    )
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)

    result = rag.generate_answer(
        "What pattern applies?",
        [{"text": "A repeated operational pattern."}],
        _config(),
        "US",
        include_memory_candidate=True,
    )

    assert isinstance(result, rag.GenerationResult)
    assert result.answer == "The repeated pattern is documented."
    assert result.memory_candidate == candidate
    assert stub.received["response_format"] == {"type": "json_object"}
    assert (
        "memory_candidate must normally be null"
        in stub.received["messages"][-1]["content"]
    )


def test_structured_generation_surfaces_only_numeric_usage_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GenerationResult.usage carries the generation model's token counts, never content."""
    usage = SimpleNamespace(prompt_tokens=500, completion_tokens=63, total_tokens=563)
    stub = _StubChat(json.dumps({"answer": "Grounded answer.", "memory_candidate": None}), usage=usage)
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)

    result = rag.generate_answer(
        "What is documented?", [{"text": "Some documented fact."}], _config(), "US", include_memory_candidate=True
    )

    assert isinstance(result, rag.GenerationResult)
    assert result.usage == {"prompt_tokens": 500, "completion_tokens": 63, "total_tokens": 563}


def test_structured_generation_usage_is_none_when_provider_omits_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _StubChat(json.dumps({"answer": "Grounded answer.", "memory_candidate": None}))
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)

    result = rag.generate_answer(
        "What is documented?", [{"text": "fact"}], _config(), "US", include_memory_candidate=True
    )
    assert isinstance(result, rag.GenerationResult)
    assert result.usage is None


def test_structured_generation_streams_only_decoded_answer_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _StubStreamingChat(
        ['{"ans', 'wer":"Hello\\n', 'world","memory_', 'candidate":null}']
    )
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)
    tokens: list[str] = []

    result = rag.generate_answer(
        "What is documented?",
        [{"text": "fact"}],
        _config(),
        "US",
        include_memory_candidate=True,
        token_callback=tokens.append,
    )

    assert isinstance(result, rag.GenerationResult)
    assert result.answer == "Hello\nworld"
    assert "".join(tokens) == "Hello\nworld"
    assert all("memory_candidate" not in token for token in tokens)
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}
    assert stub.received["stream"] is True
    assert stub.stream.closed is True


def test_streaming_generation_closes_provider_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _StubStreamingChat(['{"answer":"first', ' second","memory_candidate":null}'])
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)
    tokens: list[str] = []
    registered_closers: list[Any] = []

    with pytest.raises(rag.GenerationCancelled):
        rag.generate_answer(
            "What is documented?",
            [{"text": "fact"}],
            _config(),
            "US",
            include_memory_candidate=True,
            token_callback=tokens.append,
            cancelled=lambda: bool(tokens),
            stream_started=registered_closers.append,
        )

    assert "".join(tokens) == "first"
    assert registered_closers == [stub.stream.close]
    assert stub.stream.closed is True


def test_complete_uses_caller_system_prompt_and_returns_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete() is the drafting primitive: it sends the caller's own system prompt, not SYSTEM_PROMPT."""
    stub = _StubChat("A drafted proposal section.")
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: stub)

    result = rag.complete("You are a proposal writer.", "Draft the warehouse section.", _config())

    assert result == "A drafted proposal section."
    assert stub.received["messages"][0] == {"role": "system", "content": "You are a proposal writer."}
    assert stub.received["messages"][0]["content"] != rag.SYSTEM_PROMPT
    assert stub.received["messages"][1]["content"] == "Draft the warehouse section."


def test_complete_wraps_provider_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        def _create(self, **_kwargs: Any) -> Any:
            raise RuntimeError("deepseek down")

    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: _Boom())
    with pytest.raises(rag.RagPipelineError):
        rag.complete("sys", "user", _config())


def test_structured_generation_rejects_malformed_provider_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rag, "_chat_client", lambda *_a, **_k: _StubChat("not-json"))

    with pytest.raises(rag.RagPipelineError, match="invalid structured answer"):
        rag.generate_answer(
            "anything", [], _config(), "US", include_memory_candidate=True
        )


# --------------------------------------------------------------------------- chunking


@pytest.mark.parametrize(
    ("filename", "slug"),
    [
        ("trackflow-returns-policy.en.md", "returns-policy"),
        ("trackflow-sla-delivery.en.md", "sla-delivery"),
        ("carrier-coverage.md", "carrier-coverage"),
    ],
)
def test_source_document_slug(filename: str, slug: str) -> None:
    assert source_document_slug(filename) == slug


def test_chunk_document_keeps_list_with_its_intro() -> None:
    markdown = (
        "# Delivery SLA\n\n"
        "Delivery commitments vary by service type:\n"
        "- Standard shipping: 3 to 5 business days.\n"
        "- Express shipping: 24 to 48 hours.\n\n"
        "The committed SLA is 90% on-time per month.\n\n"
        "No SLA is guaranteed on Black Friday."
    )
    chunks = chunk_document(markdown, "sla-delivery")

    assert len(chunks) == 3
    # The bullets stayed attached to their intro sentence (rule never split).
    assert "Standard shipping" in chunks[0].text
    assert "Express shipping" in chunks[0].text
    assert chunks[0].section.startswith("Delivery SLA")
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_chunk_document_derives_labelled_section() -> None:
    markdown = "# Returns Policy\n\nStandard return window: 30 days from delivery."
    chunk = chunk_document(markdown, "returns-policy")[0]
    assert chunk.section == "Returns Policy — Standard return window"


def test_chunk_point_id_is_deterministic_and_payload_complete() -> None:
    first = Chunk(
        source_document="sla-delivery", section="Delivery SLA", chunk_index=0, text="a"
    )
    same = Chunk(
        source_document="sla-delivery", section="Different", chunk_index=0, text="b"
    )
    other = Chunk(
        source_document="sla-delivery", section="Delivery SLA", chunk_index=1, text="a"
    )

    # ID depends only on source_document + chunk_index, so re-indexing upserts in place.
    assert first.point_id == same.point_id
    assert first.point_id != other.point_id
    assert first.payload() == {
        "company": "trackflow",
        "source_document": "sla-delivery",
        "section": "Delivery SLA",
        "language": "en",
        "chunk_index": 0,
        "text": "a",
        "jurisdiction": "GLOBAL",
    }


def test_chunk_document_rejects_empty_source() -> None:
    with pytest.raises(ValueError, match="no chunks"):
        chunk_document("# Only A Title\n\n", "sla-delivery")


def test_chunk_document_glues_standalone_lists_and_colon_intros() -> None:
    markdown = (
        "# Coverage\n\n"
        "Intro without a colon\n\n"
        "- first item\n"
        "- second item\n\n"
        "Lead-in with a colon:\n\n"
        "Following paragraph\n\n"
        "- glued list item"
    )
    chunks = chunk_document(markdown, "carrier-coverage")

    assert len(chunks) == 2
    # A list separated by a blank line still attaches to the paragraph above it.
    assert "first item" in chunks[0].text and "Intro without a colon" in chunks[0].text
    # A colon lead-in pulls in the following paragraph AND its list.
    assert (
        "Following paragraph" in chunks[1].text and "glued list item" in chunks[1].text
    )


def test_chunk_document_without_h1_falls_back_to_slug_title() -> None:
    chunk = chunk_document(
        "Just a plain paragraph with no heading.", "storage-pricing"
    )[0]
    assert chunk.section == "storage-pricing"


def test_chunk_document_splits_mixed_country_policy_into_jurisdiction_chunks() -> None:
    markdown = (
        "# Carrier Coverage\n\n"
        "Coverage differs by country:\n\n"
        "United States: UPS and FedEx.\n- UPS covers California.\n\n"
        "Spain: MRW and SEUR.\n- SEUR covers Aragón.\n\n"
        "Carrier selection is automatic."
    )

    chunks = chunk_document(markdown, "carrier-coverage")

    assert [(chunk.jurisdiction, chunk.text) for chunk in chunks] == [
        (
            "US",
            "Coverage differs by country:\n\nUnited States: UPS and FedEx.\n- UPS covers California.",
        ),
        ("ES", "Spain: MRW and SEUR.\n- SEUR covers Aragón."),
        ("GLOBAL", "Carrier selection is automatic."),
    ]


# --------------------------------------------------------------------------- config / embed / setup


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QDRANT_URL", "http://qd:6333")
    monkeypatch.setenv("RAG_COLLECTION", "kb")
    monkeypatch.setenv("OPENAI_API_KEY", "oa")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
    monkeypatch.setenv("RAG_TOP_K", "7")
    monkeypatch.setenv("RAG_MIN_SCORE", "0.42")
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    cfg = rag.RagConfig.from_env()

    assert cfg.qdrant_url == "http://qd:6333"
    assert cfg.collection == "kb"
    assert cfg.qdrant_api_key is None
    assert cfg.top_k == 7
    assert cfg.min_score == 0.42


def test_embed_uses_embeddings_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _create(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    fake_client = SimpleNamespace(embeddings=SimpleNamespace(create=_create))
    monkeypatch.setattr(rag, "_embeddings_client", lambda *_a, **_k: fake_client)

    vector = rag.embed("hello", _config())

    assert vector == [0.1, 0.2, 0.3]
    assert captured["model"] == "text-embedding-3-small"
    assert captured["input"] == "hello"


def test_client_factories_require_keys() -> None:
    rag._embeddings_client.cache_clear()
    rag._chat_client.cache_clear()
    with pytest.raises(rag.RagPipelineError):
        rag._embeddings_client("")
    with pytest.raises(rag.RagPipelineError):
        rag._chat_client("", "https://api.deepseek.test")


class _StubIndexClient:
    def __init__(self, exists: bool) -> None:
        self._exists = exists
        self.created: list[str] = []
        self.deleted: list[str] = []
        self.upserted: list[Any] = []

    def collection_exists(self, name: str) -> bool:
        return self._exists

    def create_collection(self, collection_name: str, vectors_config: Any) -> None:
        self.created.append(collection_name)

    def delete_collection(self, name: str) -> None:
        self.deleted.append(name)
        self._exists = False

    def upsert(self, collection_name: str, points: list[Any]) -> None:
        self.upserted = points


def _write_corpus(tmp_path: Any) -> Any:
    (tmp_path / "trackflow-sla-delivery.en.md").write_text(
        "# Delivery SLA\n\nStandard shipping: 3 to 5 business days.\n\nNo SLA on Black Friday."
    )
    (tmp_path / "trackflow-returns-policy.en.md").write_text(
        "# Returns Policy\n\nStandard return window: 30 days.\n\nInternational returns are manual."
    )
    (tmp_path / "README.md").write_text("# ignore me")
    return tmp_path


def test_setup_indexes_corpus_idempotently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    stub = _StubIndexClient(exists=False)
    monkeypatch.setattr(rag, "_qdrant", lambda *_a, **_k: stub)
    monkeypatch.setattr(rag, "embed", lambda *_a, **_k: [0.0] * 8)

    result = rag.setup(_config(), corpus_dir=_write_corpus(tmp_path))

    assert result.documents == 2
    assert result.chunks == len(stub.upserted) == 4  # 2 chunks per doc
    assert stub.created == ["trackflow"]  # collection created because it did not exist
    ids = [point.id for point in stub.upserted]
    assert len(ids) == len(set(ids))  # deterministic, unique point IDs (README skipped)


def test_setup_recreate_drops_existing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    stub = _StubIndexClient(exists=True)
    monkeypatch.setattr(rag, "_qdrant", lambda *_a, **_k: stub)
    monkeypatch.setattr(rag, "embed", lambda *_a, **_k: [0.0] * 8)

    rag.setup(_config(), corpus_dir=_write_corpus(tmp_path), recreate=True)

    assert stub.deleted == ["trackflow"]  # dropped before rebuild
    assert stub.created == ["trackflow"]


def test_setup_rejects_empty_corpus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr(
        rag, "_qdrant", lambda *_a, **_k: _StubIndexClient(exists=False)
    )
    with pytest.raises(rag.RagPipelineError, match="No knowledge-base documents"):
        rag.setup(_config(), corpus_dir=tmp_path)
