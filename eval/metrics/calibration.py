"""校准：ECE / Brier。置信度分桶 vs 实际同向频率。"""
from __future__ import annotations


def ece(confidences: list[float], outcomes: list[int], bins: int = 5) -> float:
    raise NotImplementedError("TODO(A)")