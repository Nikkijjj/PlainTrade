"""面向用户的最终产物。UI 只渲染它，不再做任何业务判断。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .chart import ChartSpec


class ConfidencePlain(BaseModel):
    value: str
    anchor: str


class WhyPoint(BaseModel):
    point: str
    evidence: list[str] = Field(default_factory=list)
    glossary_id: str | None = None


class GlossaryTerm(BaseModel):
    id: str
    term: str
    plain: str
    analogy: str = ""


class ChartBlock(BaseModel):
    spec: ChartSpec
    image_path: str = ""


class PlainBrief(BaseModel):
    task: str
    one_liner: str
    stance_plain: str
    confidence_plain: ConfidencePlain
    why: list[WhyPoint] = Field(default_factory=list)
    charts: list[ChartBlock] = Field(default_factory=list)
    what_would_change_our_mind: list[str] = Field(default_factory=list)
    what_you_should_not_do: list[str] = Field(default_factory=list)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    audit: dict = Field(default_factory=dict)