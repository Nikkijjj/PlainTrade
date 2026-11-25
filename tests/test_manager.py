"""manager.decide 单元测试：mock 掉模型调用，锁死 no_view / 去幻觉 / 失效条件 / 降级。

真正的"汇总质量"靠 prompt + 真 key 验证；这里锁 plumbing，不依赖 key、可离线跑。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.debate import DebateResult
from agents.manager import decide
from contracts.argdoc import Claim, Evidence, Stance
from contracts.message import AgentMessage

FIX = Path("cases/fixtures/argdoc_sample.json")


def _fixture_inputs() -> tuple[dict, list[Claim], list[Evidence], list[AgentMessage], DebateResult]:
    data = json.loads(FIX.read_text(encoding="utf-8"))
    claims = [Claim(**c) for c in data["claims"]]
    evidence = [Evidence(**e) for e in data["evidence"]]
    messages = [AgentMessage(
        sender="analyst", role="analyst", task=data["task"],
        code=data["code"], as_of=data["as_of"],
        claims=claims, evidence_used=[e.id for e in evidence])]
    debate = DebateResult(bull=["看多：增速仍为正"], bear=["看空：估值偏高"])
    return data, claims, evidence, messages, debate


def test_decide_produces_valid_argdoc(monkeypatch: pytest.MonkeyPatch) -> None:
    data, claims, evidence, messages, debate = _fixture_inputs()
    draft = json.dumps({
        "stance": "mildly_positive", "confidence": 0.62,
        "claims": [c.model_dump() for c in claims],
        "counter_arguments": data["counter_arguments"],
        "invalidation_conditions": data["invalidation_conditions"],
        "information_gaps": data["information_gaps"],
        "explanation_status": "not_applicable",
    })
    monkeypatch.setattr("llm.structured.complete", lambda prompt_name, **kw: draft)
    a = decide(task="stock_outlook", code="600519", as_of="2025-01-04",
               messages=messages, debate_result=debate, evidence=evidence)
    assert a.stance == Stance.MILDLY_POSITIVE
    assert a.confidence == 0.62
    assert a.dangling_evidence() == []               # 无幻觉引用
    assert a.invalidation_conditions                 # 失效条件不能空
    assert a.evidence == evidence                    # 证据由代码注入


def test_decide_no_view_when_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list = []
    monkeypatch.setattr("llm.structured.complete",
                        lambda prompt_name, **kw: called.append(1) or "{}")
    a = decide(task="stock_outlook", code="600519", as_of="2025-01-04",
               messages=[], debate_result=None, evidence=[])
    assert a.stance == Stance.NO_VIEW
    assert a.confidence == 0.0
    assert not called                               # 证据不足，不调 LLM


def test_decide_drops_hallucinated_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    _, claims, evidence, messages, debate = _fixture_inputs()
    bad = Claim(id="h1", type="inference", text="幻觉", evidence=["ghost"])
    draft = json.dumps({
        "stance": "neutral", "confidence": 0.5,
        "claims": [c.model_dump() for c in claims] + [bad.model_dump()],
        "counter_arguments": [], "invalidation_conditions": ["某条件"],
        "information_gaps": [], "explanation_status": "not_applicable",
    })
    monkeypatch.setattr("llm.structured.complete", lambda prompt_name, **kw: draft)
    a = decide(task="stock_outlook", code="600519", as_of="2025-01-04",
               messages=messages, debate_result=debate, evidence=evidence)
    assert all("ghost" not in c.evidence for c in a.claims)


def test_decide_forces_no_view_when_no_invalidation(monkeypatch: pytest.MonkeyPatch) -> None:
    _, claims, evidence, messages, debate = _fixture_inputs()
    draft = json.dumps({
        "stance": "positive", "confidence": 0.8,
        "claims": [c.model_dump() for c in claims],
        "counter_arguments": [], "invalidation_conditions": [],   # 空 → 强制 no_view
        "information_gaps": [], "explanation_status": "not_applicable",
    })
    monkeypatch.setattr("llm.structured.complete", lambda prompt_name, **kw: draft)
    a = decide(task="stock_outlook", code="600519", as_of="2025-01-04",
               messages=messages, debate_result=debate, evidence=evidence)
    assert a.stance == Stance.NO_VIEW
    assert a.confidence == 0.0


def test_decide_llm_failure_degrades_to_no_view(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(prompt_name: str, **kw: object) -> str:
        raise RuntimeError("网络断了")

    monkeypatch.setattr("llm.structured.complete", boom)
    _, _claims, evidence, messages, debate = _fixture_inputs()
    a = decide(task="stock_outlook", code="600519", as_of="2025-01-04",
               messages=messages, debate_result=debate, evidence=evidence)
    assert a.stance == Stance.NO_VIEW
    assert a.confidence == 0.0
