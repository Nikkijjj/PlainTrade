"""公告分析师：只输出可验证事实，每条必须挂 evidence_id。"""
from __future__ import annotations

from pydantic import BaseModel

from agents.base import BaseAgent
from contracts.argdoc import Claim


class _Payload(BaseModel):
    claims: list[Claim] = []


class DisclosureAnalyst(BaseAgent):
    name = "disclosure_analyst"
    prompt_name = "analyst_disclosure"
    schema = _Payload

    def build_vars(self, ctx: dict) -> dict:
        return {"docs": ctx.get("docs", []), "financials": ctx.get("financials", {})}

    def parse(self, payload, ctx: dict) -> list[Claim]:
        return [c for c in payload.claims if c.type == "fact"]