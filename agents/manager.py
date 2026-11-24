"""研究经理：唯一有权输出 stance 的 agent，汇总成 ArgDoc。"""
from __future__ import annotations

from contracts.argdoc import ArgDoc


def decide(*, task: str, code: str | None, as_of: str,
           messages: list, debate_result, evidence: list) -> ArgDoc:
    """裁决分歧并写 invalidation_conditions / information_gaps；
    证据不足必须 stance=no_view，confidence 与 information_gaps 数量负相关。
    """
    raise NotImplementedError("TODO(B)")