"""三个问题模板：入口只是问题模板，共用一条管线。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TaskTemplate:
    task: str
    label: str
    example: str
    needs_docs: bool = True
    needs_financials: bool = True
    needs_signals: bool = False
    chart_hint: str = "risk"
    extra: dict = field(default_factory=dict)


TASKS = {
    "market_event": TaskTemplate(
        task="market_event", label="今天怎么了",
        example="今天科技股跌这么多，怎么了？",
        needs_financials=False, needs_signals=True, chart_hint="attribution"),
    "stock_outlook": TaskTemplate(
        task="stock_outlook", label="这只怎么样",
        example="600519 这只怎么样？", chart_hint="risk"),
    "allocation_literacy": TaskTemplate(
        task="allocation_literacy", label="钱怎么放",
        example="我手上有 10 万，该怎么分配？",
        needs_docs=False, needs_financials=False, chart_hint="allocation"),
}