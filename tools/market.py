"""行情类工具：日线、交易日。"""
from __future__ import annotations

from contracts.tool import ToolSpec
from data import db
from tools.registry import register


def get_series(code: str, start: str, end: str, adj: str = "hfq") -> list[dict]:
    return db.series(code, start, end, adj).to_dict("records")


def get_trade_dates(start: str, end: str) -> list[str]:
    return db.trade_dates(start, end)


register(ToolSpec(
    name="get_series", description="取某只股票的日线序列（默认后复权）",
    params_schema={"type": "object",
                   "properties": {"code": {"type": "string"},
                                  "start": {"type": "string"},
                                  "end": {"type": "string"},
                                  "adj": {"type": "string", "enum": ["hfq", "qfq"]}},
                   "required": ["code", "start", "end"]},
    returns="list[{date, open, high, low, close, volume, amount}]", timeout_s=15,
), get_series)

register(ToolSpec(
    name="get_trade_dates", description="取区间内交易日列表",
    params_schema={"type": "object",
                   "properties": {"start": {"type": "string"}, "end": {"type": "string"}},
                   "required": ["start", "end"]},
    returns="list[str]", timeout_s=10,
), get_trade_dates)