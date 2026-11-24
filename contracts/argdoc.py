"""研究层产物：一份带证据的论证结构。与任务类型无关，适配层只消费它。"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Stance(str, Enum):
    POSITIVE = "positive"
    MILDLY_POSITIVE = "mildly_positive"
    NEUTRAL = "neutral"
    MILDLY_NEGATIVE = "mildly_negative"
    NEGATIVE = "negative"
    NO_VIEW = "no_view"


class ExplanationStatus(str, Enum):
    SINGLE_CAUSE = "single_cause"
    MULTIPLE_CANDIDATES = "multiple_candidates"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Evidence(BaseModel):
    id: str
    source: str
    doc_type: Literal["announcement", "report", "news", "market_data"]
    publish_time: str            # ISO 或 'YYYY-MM-DD'，只认它做 as-of 判断
    quote: str = ""
    url: str = ""


class Claim(BaseModel):
    id: str
    type: Literal["fact", "inference"]
    text: str
    evidence: list[str] = Field(default_factory=list)


class ArgDoc(BaseModel):
    task: Literal["market_event", "stock_outlook", "allocation_literacy"]
    code: str | None = None
    as_of: str
    horizon: str = "4w"
    stance: Stance = Stance.NO_VIEW
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    claims: list[Claim] = Field(default_factory=list)
    counter_arguments: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    explanation_status: ExplanationStatus = ExplanationStatus.NOT_APPLICABLE
    evidence: list[Evidence] = Field(default_factory=list)
    audit: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _no_leakage(self) -> "ArgDoc":
        """保守时间规则：与 as_of 同日或更晚的证据一律视为泄漏。"""
        as_of_day = self.as_of[:10]
        for e in self.evidence:
            if e.publish_time[:10] >= as_of_day:
                raise ValueError(
                    f"证据 {e.id} 的 publish_time={e.publish_time} 不早于 as_of={as_of_day}，属未来信息"
                )
        return self

    def evidence_map(self) -> dict[str, Evidence]:
        return {e.id: e for e in self.evidence}

    def dangling_evidence(self) -> list[str]:
        """引用了不存在的 evidence_id（幻觉），必须为空。"""
        known = set(self.evidence_map())
        return [eid for c in self.claims for eid in c.evidence if eid not in known]