"""术语门控：检测行话 -> 挂解释卡 -> 复检 -> 重写（上限 3 轮）。"""
from __future__ import annotations


def detect(text: str, terms: list[dict] | None = None) -> list[dict]:
    """返回命中的、尚未解释的术语。"""
    raise NotImplementedError("TODO(C)")


def enforce(text: str, max_rounds: int = 3) -> tuple[str, int]:
    """返回 (改后文本, 实际轮数)；超轮数则降级到去术语模板。"""
    raise NotImplementedError("TODO(C)")