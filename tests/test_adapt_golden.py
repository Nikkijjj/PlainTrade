"""适配层 golden case：置信度映射必须与设计表一致。"""
from __future__ import annotations

import pytest

from adapt.summarize import plain_confidence


@pytest.mark.parametrize("conf,value", [
    (0.85, "比较有把握"),
    (0.70, "比较有把握"),
    (0.62, "大概六成"),
    (0.55, "大概六成"),
    (0.50, "说不出高下"),
    (0.45, "说不出高下"),
    (0.30, "没有明确看法"),
])
def test_confidence_bands(conf: float, value: str) -> None:
    assert plain_confidence(conf).value == value


def test_anchor_carries_reference() -> None:
    """置信度必须配参照系，不能只给数字。"""
    assert "抛硬币" in plain_confidence(0.62).anchor