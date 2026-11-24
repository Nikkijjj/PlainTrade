"""文本加工：中文分词与 FTS 查询表达式。

为什么放在 data/：分词是数据加工，入库建索引与查询必须用同一份实现，
否则 BM25 打分不可比。research/ 也依赖它（依赖方向 research -> data）。
"""
from __future__ import annotations

import re

_CJK = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")


def _bigrams(text: str) -> str:
    """jieba 缺失时的降级方案：中文取 2-gram，英文数字取整词。

    好处：FTS5 unicode61 下也能命中中文子串；坏处：词边界不准，BM25 略差。
    """
    tokens: list[str] = []
    for chunk in _CJK.findall(text):
        if chunk[0].isascii():
            tokens.append(chunk)
        elif len(chunk) == 1:
            tokens.append(chunk)
        else:
            tokens.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
    return " ".join(tokens)


def tokenize(text: str) -> str:
    """jieba 预分词，空格连接；没有 jieba 就用 2-gram 降级。"""
    if not text:
        return ""
    try:
        import jieba
    except ImportError:
        return _bigrams(text)
    return " ".join(t.strip() for t in jieba.cut(text) if t.strip())


def fts_expr(query: str) -> str:
    """把查询词变成 FTS5 表达式（OR 语义，保召回）。"""
    toks = [t for t in tokenize(query).split() if t]
    return " OR ".join(toks) or query