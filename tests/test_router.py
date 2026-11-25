"""Router 单元测试：mock 掉模型调用，锁死解析 / 修复 / 兜底逻辑。

真正的"分类正确性"靠 prompt + 真 key 验证（见 docs/用户问题测试用例.md），
这里只锁 plumbing（extract_json / complete_json / route 兜底），不依赖 key、可离线跑。
"""
from __future__ import annotations

import pytest

from agents.router import RouteResult, route
from llm.structured import StructuredOutputError, complete_json, extract_json


# ── extract_json ──────────────────────────────────────
def test_extract_json_bare() -> None:
    assert extract_json('{"task":"chit_chat"}') == {"task": "chit_chat"}


def test_extract_json_fenced() -> None:
    raw = '```json\n{"task":"stock_outlook","code":"600519"}\n```'
    assert extract_json(raw) == {"task": "stock_outlook", "code": "600519"}


def test_extract_json_with_chatter() -> None:
    raw = '好的，判断结果是 {"task":"market_event"} 就这样'
    assert extract_json(raw) == {"task": "market_event"}


def test_extract_json_garbage_raises() -> None:
    with pytest.raises(ValueError):
        extract_json("没有 JSON 对象")


# ── complete_json 修复回喂 ────────────────────────────
def test_complete_json_recovers_on_bad_first(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []

    def fake(prompt_name: str, **kw: object) -> str:
        calls.append(kw.get("extra_instruction"))
        return "bad" if len(calls) == 1 else '{"task":"chit_chat"}'

    monkeypatch.setattr("llm.structured.complete", fake)
    r = complete_json("router", RouteResult, user_text="hi", as_of="", page_hint="")
    assert r.task == "chit_chat"
    assert len(calls) == 2                       # 首次 + 一次修复
    assert calls[1] and "无法通过校验" in calls[1]


def test_complete_json_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm.structured.complete", lambda prompt_name, **kw: "garbage")
    with pytest.raises(StructuredOutputError):
        complete_json("router", RouteResult, user_text="hi", as_of="", page_hint="")


# ── route() 正常解析 ──────────────────────────────────
def test_route_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "llm.structured.complete",
        lambda prompt_name, **kw: '{"task":"stock_outlook","code":"600519",'
                                   '"as_of":"2025-01-04","is_panic":false}')
    r = route("600519 这只怎么样？", as_of="2025-01-04")
    assert r == RouteResult(task="stock_outlook", code="600519",
                            as_of="2025-01-04", is_panic=False)


def test_route_panic_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "llm.structured.complete",
        lambda prompt_name, **kw: '{"task":"market_event","as_of":"2025-01-04","is_panic":true}')
    r = route("跌懵了", as_of="2025-01-04")
    assert r.is_panic is True
    assert r.task == "market_event"


# ── route() 兜底（模型挂了也不能崩）───────────────────
def test_route_fallback_default(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(prompt_name: str, **kw: object) -> str:
        raise RuntimeError("网络断了")

    monkeypatch.setattr("llm.structured.complete", boom)
    r = route("随便", as_of="2025-01-04")
    assert r.task == "stock_outlook"
    assert r.as_of == "2025-01-04"


def test_route_fallback_uses_page_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(prompt_name: str, **kw: object) -> str:
        raise RuntimeError("网络断了")

    monkeypatch.setattr("llm.structured.complete", boom)
    r = route("随便", as_of="2025-01-04", page_hint="market_event")
    assert r.task == "market_event"
