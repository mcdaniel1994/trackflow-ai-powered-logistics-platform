"""RFP intake agents (LLM structured output mocked; orchestrator/synthesizer deterministic)."""

from __future__ import annotations

import pytest

from central_api.domains.rfp import agents
from central_api.domains.rfp.agents import (
    RfpAgentError,
    _Classification,
    _KeyAspects,
    _Metadata,
    classify_document,
    currency_for,
    extract_key_aspects,
    extract_metadata,
    plan_departments,
    synthesize_routing,
)
from central_api.domains.rfp.config import RfpConfig

CFG = RfpConfig(model="m", timeout_seconds=1.0, openai_api_key="k")
PRICED_CFG = RfpConfig(model="gpt-4o-mini", timeout_seconds=1.0, openai_api_key="k")


def test_classify_maps_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agents, "_invoke_structured", lambda *a, **k: (_Classification(is_rfp=True, reason="client asks"), None)
    )
    result, _usage = classify_document("doc", CFG)
    assert result.is_rfp is True and result.reason == "client asks"


def test_extract_dedupes_services_and_derives_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agents,
        "_invoke_structured",
        lambda *a, **k: (
            _Metadata(
                client_name="Luna",
                client_country="US",
                services_requested=["warehousing", "warehousing", "lastmile"],
                monthly_volume=5000,
                deadline_days=20,
            ),
            None,
        ),
    )
    result, _usage = extract_metadata("doc", CFG)
    assert result.services_requested == ["warehousing", "lastmile"]
    assert currency_for(result.client_country) == "USD"


def test_worker_trims_and_caps_aspects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agents,
        "_invoke_structured",
        lambda *a, **k: (_KeyAspects(aspects=["  storage capacity  ", "", "onboarding time"]), None),
    )
    aspects, _usage = extract_key_aspects("warehouse", "doc", CFG)
    assert aspects == ["storage capacity", "onboarding time"]


def test_plan_departments_maps_and_dedupes() -> None:
    assert plan_departments(["warehousing", "returns", "warehousing"]) == ["warehouse", "reverse"]
    assert plan_departments(["lastmile"]) == ["lastmile"]
    assert plan_departments([]) == []


def test_currency_for() -> None:
    assert currency_for("US") == "USD"
    assert currency_for("ES") == "EUR"
    assert currency_for(None) is None
    assert currency_for("XX") is None


def test_synthesize_routing_shape() -> None:
    summary = synthesize_routing({"warehouse": ["capacity"], "reverse": ["turnaround"]})
    ids = [entry["department_id"] for entry in summary["departments"]]  # type: ignore[index]
    assert ids == ["warehouse", "reverse"]


def test_missing_key_raises() -> None:
    with pytest.raises(RfpAgentError):
        classify_document("doc", RfpConfig(model="m", timeout_seconds=1.0, openai_api_key=""))


class _FakeMessage:
    """Stands in for a LangChain ``AIMessage`` carrying standardized token counters."""

    def __init__(self, usage_metadata: dict | None = None) -> None:
        self.usage_metadata = usage_metadata or {}
        self.response_metadata: dict = {}


class _FakeLLM:
    def __init__(
        self,
        parsed: object = None,
        *,
        boom: bool = False,
        parsing_error: object = None,
        usage: dict | None = None,
    ) -> None:
        self._parsed = parsed
        self._boom = boom
        self._parsing_error = parsing_error
        self._usage = usage

    def with_structured_output(self, _schema: object, include_raw: bool = False) -> _FakeLLM:
        return self

    def invoke(self, _messages: object) -> object:
        if self._boom:
            raise RuntimeError("provider down")
        return {
            "raw": _FakeMessage(self._usage),
            "parsed": self._parsed,
            "parsing_error": self._parsing_error,
        }


def test_invoke_structured_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_chat", lambda _cfg: _FakeLLM(_Classification(is_rfp=True, reason="ok")))
    result, _usage = classify_document("doc", CFG)
    assert result.is_rfp is True


def test_invoke_structured_captures_priced_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    monkeypatch.setattr(
        agents, "_chat", lambda _cfg: _FakeLLM(_Classification(is_rfp=True, reason="ok"), usage=usage)
    )
    _result, model_usage = classify_document("doc", PRICED_CFG)
    assert model_usage is not None
    assert model_usage.total_tokens == 15
    assert model_usage.cost_usd is not None  # gpt-4o-mini is priced


def test_invoke_structured_translates_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_chat", lambda _cfg: _FakeLLM(boom=True))
    with pytest.raises(RfpAgentError):
        classify_document("doc", CFG)


def test_invoke_structured_rejects_unexpected_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_chat", lambda _cfg: _FakeLLM("not a model"))
    with pytest.raises(RfpAgentError):
        extract_metadata("doc", CFG)


def test_invoke_structured_raises_on_parsing_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agents, "_chat", lambda _cfg: _FakeLLM(_Classification(is_rfp=True, reason="ok"), parsing_error="bad")
    )
    with pytest.raises(RfpAgentError):
        classify_document("doc", CFG)
