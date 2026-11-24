"""token 与美元记账。单价按模型名匹配，未知模型按最贵算（避免低估成本）。"""
from __future__ import annotations

# 单位：美元 / 1M tokens（input, output）
PRICE = {
    "deepseek-chat": (0.27, 1.10),
    "qwen-max": (2.40, 9.60),
}
DEFAULT = (2.40, 9.60)


def usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICE.get(model, DEFAULT)
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000