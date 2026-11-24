"""越界检测：买卖指令 / 具体参数 / 时序指令 / 绝对断言 / 配置比例。

两轮未通过 -> 拒答（宁可不出，不可越界）。
"""
from __future__ import annotations

import re

# ① 直接命中的词（子串）
BANNED = (
    "建议买入", "建议卖出", "加仓", "减仓", "清仓", "抄底", "逢低", "建仓",
    "目标价", "止盈", "止损", "半仓", "满仓",
    "必涨", "稳赚", "无风险", "保证收益", "上车",
)

# ② 模式规则（词表覆盖不到的组合）
PATTERNS = (
    # 时序指令：明天开盘买 / 下周建仓
    (r"(明|今|后|下)(天|日|周|月)?.{0,4}(买|卖|建仓|加仓|减仓|清仓)", "时序指令"),
    # 建议 + 动作：建议配置 / 建议买 / 建议卖
    (r"建议.{0,6}(买|卖|配置|持有|加码)", "买卖建议"),
    # 你的仓位/你的资金 + 动词
    (r"(你|您的).{0,4}(仓位|资金|资金量).{0,6}(应|要|可以)", "个人化配置"),
    # 比例 + 配置类动词：配置 30% / 三成仓
    (r"(\d+\s*%|百分之[一二三四五六七八九十\d]+|[一二三四五六七八九十]成).{0,8}"
     r"(配置|仓位|资金|买|投|放)", "具体比例"),
)

REFUSAL = (
    "这个问题我给不出一个不越界的答案。"
    "我能做的是：把可确认的事实、可能的原因、以及我们不知道的部分讲清楚，判断留给你。"
)


def check(text: str) -> list[str]:
    """返回命中的越界片段（词 + 模式）；空列表 = 通过。"""
    hits = [w for w in BANNED if w in text]
    for pattern, label in PATTERNS:
        for m in re.finditer(pattern, text):
            hits.append(f"{label}:{m.group(0)}")
    return hits


def enforce(text: str, max_rounds: int = 2) -> tuple[str, bool]:
    """返回 (处理后的文本, 是否被拒答)。重写由 llm 完成，这里给结构与兜底。"""
    if not check(text):
        return text, False
    if max_rounds <= 0:
        return REFUSAL, True
    return text, False          # TODO(C): 接 llm 重写后再递归 enforce(max_rounds-1)