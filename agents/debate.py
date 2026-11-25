"""Bull / Bear 单轮反驳。硬规则：不得引入新事实，只能引用已有 evidence_id。"""
from __future__ import annotations

import json

from pydantic import BaseModel

from llm.structured import complete_json


class DebateResult(BaseModel):
    bull: list[str] = []
    bear: list[str] = []
    invalidation_conditions: list[str] = []


class _Bull(BaseModel):
    rebuttals: list[str] = []


class _Bear(BaseModel):
    rebuttals: list[str] = []
    invalidation_conditions: list[str] = []


def _claims_json(claims: list) -> str:
    return json.dumps(
        [c.model_dump() if hasattr(c, "model_dump") else c for c in claims],
        ensure_ascii=False, indent=2, default=str)


def debate(claims: list, evidence_ids: list[str], rounds: int = 1) -> DebateResult:
    """Bull / Bear 各调一次；任一失败都降级为空（经理直接汇总，不阻塞链路）。"""
    vars_ = {"claims": _claims_json(claims),
             "evidence_ids": ", ".join(evidence_ids) or "（无）"}
    try:
        bull = complete_json("debate_bull", _Bull, **vars_)
    except Exception:                             # noqa: BLE001
        bull = _Bull()
    try:
        bear = complete_json("debate_bear", _Bear, **vars_)
    except Exception:                             # noqa: BLE001
        bear = _Bear()
    return DebateResult(bull=bull.rebuttals, bear=bear.rebuttals,
                        invalidation_conditions=bear.invalidation_conditions)
