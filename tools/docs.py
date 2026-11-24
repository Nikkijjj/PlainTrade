"""文档类工具：公告与全文检索。"""
from __future__ import annotations

from contracts.tool import ToolSpec
from data import db
from tools.registry import register


def get_announcements(code: str, as_of: str, k: int = 10) -> list[dict]:
    return db.asof_docs(code, as_of, k)


def search_docs(query: str, as_of: str, k: int = 10) -> list[dict]:
    return db.search_docs(query, as_of, k)


register(ToolSpec(
    name="get_announcements", description="取 as_of 之前已披露的公告",
    params_schema={"type": "object",
                   "properties": {"code": {"type": "string"},
                                  "as_of": {"type": "string"},
                                  "k": {"type": "integer"}},
                   "required": ["code", "as_of"]},
    returns="list[{art_code, title, notice_date, publish_time, content}]", timeout_s=15,
), get_announcements)

register(ToolSpec(
    name="search_docs", description="在 as_of 之前的公告正文里做全文检索（BM25）",
    params_schema={"type": "object",
                   "properties": {"query": {"type": "string"},
                                  "as_of": {"type": "string"},
                                  "k": {"type": "integer"}},
                   "required": ["query", "as_of"]},
    returns="list[{doc_id, title, snippet, score}]", timeout_s=15,
), search_docs)