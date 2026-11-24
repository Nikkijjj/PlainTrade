"""基本面分析师：只做推断（type=inference）。"""
from __future__ import annotations

from pydantic import BaseModel

from agents.base import BaseAgent
from contracts.argdoc import Claim


class _Payload(BaseModel):
    claims: list[Claim] = []


class FundamentalAnalyst(BaseAgent):
    name = "fundamental_analyst"
    prompt_name = "analyst_fundamental"
    schema = _Payload

    def build_vars(self, ctx: dict) -> dict:
        return {"financials": ctx.get("financials", {})}

    def parse(self, payload, ctx: dict) -> list[Claim]:
        return list(payload.claims)