"""pipeline.run 冒烟测试：mock 掉 router，验证短路与组装不崩（离线）。"""
from __future__ import annotations

import pytest

from agents.router import RouteResult
from pipeline.run import run


def test_run_chit_chat_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    """寒暄短路：不取数、不调分析师，只做一次轻量 LLM 回一句。"""
    monkeypatch.setattr("pipeline.run.route",
                        lambda user_text, as_of=None: RouteResult(task="chit_chat", as_of=as_of))
    monkeypatch.setattr("llm.structured.complete",
                        lambda prompt_name, **kw: '{"one_liner":"你好！我能帮你看市场、个股、怎么分配钱。"}')
    b = run("你好", "2025-01-04")
    assert b.task == "chit_chat"
    assert "你好" in b.one_liner
    assert b.charts == []


def test_run_chit_chat_llm_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """chit_chat 的 LLM 挂了要落兜底话术，不能崩。"""
    monkeypatch.setattr("pipeline.run.route",
                        lambda user_text, as_of=None: RouteResult(task="chit_chat", as_of=as_of))
    def boom(prompt_name: str, **kw: object) -> str:
        raise RuntimeError("网络断")
    monkeypatch.setattr("llm.structured.complete", boom)
    b = run("珠穆朗玛峰多高", "2025-01-04")
    assert b.task == "chit_chat"
    assert "PlainTrade" in b.one_liner
