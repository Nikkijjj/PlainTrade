"""越界检测：8 类禁用表达必须全部命中。"""
from __future__ import annotations

import pytest

from guardrails.escalation import check, enforce


@pytest.mark.parametrize("text", [
    "建议买入并持有",
    "目标价 120 元",
    "可以半仓",
    "这只股票必涨",
    "稳赚不赔",
    "明天开盘买",
    "无风险套利",
    "建议配置 30% 到白酒",
])
def test_banned_hit(text: str) -> None:
    assert check(text), f"未命中越界表达：{text}"


def test_clean_text_passes() -> None:
    assert check("这家公司收入同比增长 12%，但增速在回落") == []


def test_reject_after_max_rounds() -> None:
    text, rejected = enforce("建议买入", max_rounds=0)
    assert rejected is True and "越界" in text