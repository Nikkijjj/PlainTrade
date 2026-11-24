"""技术分析师：只描述，不给操作点位。指标由代码算好喂入。"""
from __future__ import annotations

from pydantic import BaseModel

from agents.base import BaseAgent
from contracts.argdoc import Claim


class _Payload(BaseModel):
    claims: list[Claim] = []


class TechnicalAnalyst(BaseAgent):
    name = "technical_analyst"
    prompt_name = "analyst_technical"
    schema = _Payload

    def build_vars(self, ctx: dict) -> dict:
        return {"indicators": ctx.get("indicators", {})}

    def parse(self, payload, ctx: dict) -> list[Claim]:
        return list(payload.claims)