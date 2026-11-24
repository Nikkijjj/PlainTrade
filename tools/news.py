"""新闻类工具：仅近端。历史决策点禁止调用（前视偏差）。"""
from __future__ import annotations

from contracts.tool import ToolSpec
from data import db
from tools.registry import register


def get_recent_news(since: str, keyword: str | None = None, k: int = 20) -> list[dict]:
    return db.news_since(since, keyword, k)


register(ToolSpec(
    name="get_recent_news",
    description="取最近新闻（仅限近端实时场景，不可用于历史决策点）",
    params_schema={"type": "object",
                   "properties": {"since": {"type": "string"},
                                  "keyword": {"type": "string"},
                                  "k": {"type": "integer"}},
                   "required": ["since"]},
    returns="list[{time, title, summary, media, url}]", timeout_s=20,
), get_recent_news)