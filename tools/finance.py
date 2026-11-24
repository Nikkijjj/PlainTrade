"""财务类工具。"""
from __future__ import annotations

from contracts.tool import ToolSpec
from data import db
from tools.registry import register


def get_financials(code: str, as_of: str) -> dict:
    return db.asof_financials(code, as_of)


register(ToolSpec(
    name="get_financials", description="取 as_of 之前已披露的财务指标",
    params_schema={"type": "object",
                   "properties": {"code": {"type": "string"}, "as_of": {"type": "string"}},
                   "required": ["code", "as_of"]},
    returns="dict[item, value]", timeout_s=15,
), get_financials)