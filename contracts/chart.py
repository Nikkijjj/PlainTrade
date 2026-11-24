"""图表决策对象：只描述要不要出图、出哪种、为什么，不含任何数值。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ChartDecision(str, Enum):
    EMIT = "emit"
    SKIP = "skip"


class NeedType(str, Enum):
    TREND = "trend"
    COMPARE = "compare"
    RISK = "risk"
    ALLOCATION = "allocation"
    ATTRIBUTION = "attribution"
    NO_ATTRIBUTION = "no_attribution"


CHART_TYPE_BY_NEED = {
    NeedType.TREND: "line",
    NeedType.COMPARE: "relative_line",
    NeedType.RISK: "drawdown_curve",
    NeedType.ALLOCATION: "stacked_bar",
    NeedType.ATTRIBUTION: "bar",
    NeedType.NO_ATTRIBUTION: None,
}


class ChartSpec(BaseModel):
    decision: ChartDecision
    need_type: NeedType
    chart_type: str | None = None
    data_ref: str = ""
    annotations: list[str] = Field(default_factory=list)
    caption: str = ""
    reason: str = ""

    @model_validator(mode="after")
    def _check(self) -> "ChartSpec":
        if self.need_type is NeedType.NO_ATTRIBUTION and self.decision is not ChartDecision.SKIP:
            raise ValueError("need_type=no_attribution 时必须 decision=skip")
        if self.decision is ChartDecision.SKIP:
            if not self.reason:
                raise ValueError("decision=skip 必须给 reason")
        else:
            if not self.caption:
                raise ValueError("decision=emit 必须给 caption")
            if not self.chart_type:
                self.chart_type = CHART_TYPE_BY_NEED.get(self.need_type)
        return self