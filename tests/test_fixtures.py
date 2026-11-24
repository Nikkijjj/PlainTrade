"""fixtures 不能烂：每次 pytest 都验证它们能通过契约校验。

作用：C 和 A 拿 fixtures 开发时，如果有人偷偷改了 contracts 字段，
这里会立刻报错，而不是等集成那天才发现"渲染不出来了"。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.argdoc import ArgDoc
from contracts.brief import PlainBrief

FIXTURES = Path(__file__).resolve().parent.parent / "cases" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _clean(d: dict) -> dict:
    """去掉以 _ 开头的注释字段（契约不允许未知字段时会被拒）。"""
    return {k: v for k, v in d.items() if not k.startswith("_")}


@pytest.mark.parametrize("name", ["argdoc_sample.json", "argdoc_unknown.json"])
def test_argdoc_fixture_valid(name: str) -> None:
    doc = ArgDoc(**_clean(_load(name)))
    assert doc.dangling_evidence() == [], "fixture 里有引用不存在的 evidence_id"


@pytest.mark.parametrize("name", ["plainbrief_sample.json", "plainbrief_nochart.json"])
def test_plainbrief_fixture_valid(name: str) -> None:
    brief = PlainBrief(**_clean(_load(name)))
    assert brief.one_liner and brief.stance_plain
    for block in brief.charts:
        if block.spec.decision.value == "emit":
            assert block.spec.caption, "出图必须带 caption"


def test_unknown_attribution_fixture_must_skip_chart() -> None:
    """最关键的一条：归因不明时 fixture 必须是 skip。"""
    brief = PlainBrief(**_clean(_load("plainbrief_nochart.json")))
    specs = [b.spec for b in brief.charts]
    assert specs, "fixture 应包含一个图表决策（即便是 skip）"
    assert all(s.decision.value == "skip" for s in specs)


def test_argdoc_unknown_has_no_view() -> None:
    doc = ArgDoc(**_clean(_load("argdoc_unknown.json")))
    assert doc.stance.value == "no_view"
    assert doc.explanation_status.value == "unknown"


def test_skip_spec_requires_reason() -> None:
    """契约层强制：skip 必须有 reason，否则等于"悄悄不出图"。"""
    with pytest.raises(Exception):
        PlainBrief(**_clean({
            "task": "market_event", "one_liner": "x", "stance_plain": "y",
            "confidence_plain": {"value": "v", "anchor": "a"},
            "charts": [{"spec": {"decision": "skip", "need_type": "no_attribution"},
                        "image_path": ""}],
        }))
