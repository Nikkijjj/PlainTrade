"""检索层：FTS5 BM25 查询。分词实现放在 data/text.py（单一实现，避免打分不可比）。"""
from __future__ import annotations

from data import db
from data.text import fts_expr, tokenize

__all__ = ["tokenize", "fts_expr", "search"]


def search(query: str, as_of: str, k: int = 10) -> list[dict]:
    """等价于 db.search_docs，保留本函数便于 research 层单独演化。"""
    return db.search_docs(query, as_of, k)