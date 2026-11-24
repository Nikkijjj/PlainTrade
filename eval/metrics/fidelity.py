"""扭曲率 = distorted / 总判定数。需人工抽检 80 条算 Cohen's kappa。"""
from __future__ import annotations


def distortion_rate(judgements: list[str]) -> float:
    raise NotImplementedError("TODO(A)")