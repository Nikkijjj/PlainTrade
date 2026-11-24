"""图表必要性 / 视觉过度归因率 / 元素完整率。过度归因目标 < 10%。"""
from __future__ import annotations


def over_attribution_rate(specs: list[dict]) -> float:
    """explanation_status=unknown 却 emit 的比例。"""
    raise NotImplementedError("TODO(A)")