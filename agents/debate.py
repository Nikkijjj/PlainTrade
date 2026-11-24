"""Bull / Bear 单轮反驳。硬规则：不得引入新事实，只能引用已有 evidence_id。"""
from __future__ import annotations

from pydantic import BaseModel


class DebateResult(BaseModel):
    bull: list[str] = []
    bear: list[str] = []
    invalidation_conditions: list[str] = []


def debate(claims: list, evidence_ids: list[str], rounds: int = 1) -> DebateResult:
    """失败可返回空 DebateResult（降级可接受，经理直接汇总）。"""
    raise NotImplementedError("TODO(B)")