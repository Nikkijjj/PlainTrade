"""ChartPlanner：决定要不要出图、出哪种、为什么。不产出任何数值。"""
from __future__ import annotations

from contracts.argdoc import ExplanationStatus
from contracts.chart import ChartDecision, ChartSpec, NeedType


def plan(argdoc) -> ChartSpec:
    """归因不明时硬性不出图（视觉过度归因）。"""
    if argdoc.explanation_status is ExplanationStatus.UNKNOWN:
        return ChartSpec(decision=ChartDecision.SKIP, need_type=NeedType.NO_ATTRIBUTION,
                         reason="归因状态为 unknown，出图会造成确定性错觉")
    raise NotImplementedError("TODO(C): 其余按论证需求分类走 chart_contracts.yaml")