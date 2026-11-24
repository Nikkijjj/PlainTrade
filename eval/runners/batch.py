"""批量跑多个条件（B1 朴素prompt / B2 无图 / B3 选择性出图 / B4 永远出图）。"""
from __future__ import annotations


def run_batch(conditions: list[str], codes: list[str], dates: list[str]) -> list[dict]:
    raise NotImplementedError("TODO(A)")