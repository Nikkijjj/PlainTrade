"""三层归因（仅事件场景）：已确认事实 / 相关信号 / 我们不知道。

历史事件拿不到新闻，中间层用可核验的市场信号（隔夜外盘、板块同向跌幅）。
"""
from __future__ import annotations


def layer(facts: dict, signals: dict) -> dict:
    """返回 {'facts': [...], 'signals': [...], 'unknown': [...]}"""
    raise NotImplementedError("TODO(C)")