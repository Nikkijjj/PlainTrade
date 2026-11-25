"""ChartPlanner：决定要不要出图、出哪种、为什么。不产出任何数值。"""
from __future__ import annotations

from contracts.argdoc import ExplanationStatus, Stance
from contracts.chart import ChartDecision, ChartSpec, NeedType


def plan(argdoc) -> ChartSpec:
    """归因不明/无结论时硬性不出图（视觉过度归因）；其余按 task 分类。

    D-03 用最小规则版；D-05（C）再换成 chart_contracts.yaml 全量分类。
    """
    if argdoc.explanation_status is ExplanationStatus.UNKNOWN:
        return ChartSpec(decision=ChartDecision.SKIP, need_type=NeedType.NO_ATTRIBUTION,
                         reason="归因状态为 unknown，出图会造成确定性错觉")
    if argdoc.stance is Stance.NO_VIEW:
        return ChartSpec(decision=ChartDecision.SKIP, need_type=NeedType.NO_ATTRIBUTION,
                         reason="无明确结论，不出图（避免视觉暗示方向）")

    if argdoc.task == "market_event":
        return ChartSpec(decision=ChartDecision.EMIT, need_type=NeedType.ATTRIBUTION,
                         data_ref="board_pct_changes",
                         caption="当日各板块涨跌幅（按幅度排序）")
    if argdoc.task == "stock_outlook" and argdoc.code:
        return ChartSpec(decision=ChartDecision.EMIT, need_type=NeedType.RISK,
                         data_ref=f"series:{argdoc.code}",
                         caption="近一年回撤曲线（从历史高点算起）")
    # allocation_literacy 是规则类，无市场数据可画
    return ChartSpec(decision=ChartDecision.SKIP, need_type=NeedType.NO_ATTRIBUTION,
                     reason="规则类问题，无市场数据可画")
