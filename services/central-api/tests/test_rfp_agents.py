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


def test_classify_maps_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agents, "_invoke_structured", lambda *a, **k: _Classification(is_rfp=True, reason="client asks")
    )
    result = classify_document("doc", CFG)
    assert result.is_rfp is True and result.reason == "client asks"


def test_extract_dedupes_services_and_derives_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agents,
        "_invoke_structured",
        lambda *a, **k: _Metadata(
            client_name="Luna",
            client_country="US",
            services_requested=["warehousing", "warehousing", "lastmile"],
            monthly_volume=5000,
            deadline_days=20,
        ),
    )
    result = extract_metadata("doc", CFG)
    assert result.services_requested == ["warehousing", "lastmile"]
    assert currency_for(result.client_country) == "USD"


def test_worker_trims_and_caps_aspects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agents,
        "_invoke_structured",
        lambda *a, **k: _KeyAspects(aspects=["  storage capacity  ", "", "onboarding time"]),
    )
    assert extract_key_aspects("warehouse", "doc", CFG) == ["storage capacity", "onboarding time"]


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


class _FakeLLM:
    def __init__(self, result: object = None, *, boom: bool = False) -> None:
        self._result = result
        self._boom = boom

    def with_structured_output(self, _schema: object) -> _FakeLLM:
        return self

    def invoke(self, _messages: object) -> object:
        if self._boom:
            raise RuntimeError("provider down")
        return self._result


def test_invoke_structured_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_chat", lambda _cfg: _FakeLLM(_Classification(is_rfp=True, reason="ok")))
    assert classify_document("doc", CFG).is_rfp is True


def test_invoke_structured_translates_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_chat", lambda _cfg: _FakeLLM(boom=True))
    with pytest.raises(RfpAgentError):
        classify_document("doc", CFG)


def test_invoke_structured_rejects_unexpected_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "_chat", lambda _cfg: _FakeLLM("not a model"))
    with pytest.raises(RfpAgentError):
        extract_metadata("doc", CFG)
