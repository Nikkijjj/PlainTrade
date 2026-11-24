"""Router：判定 task + 抽实体。全系统唯一决定"这是哪类问题"的地方。"""
from __future__ import annotations

from pydantic import BaseModel

from llm.structured import complete_json


class RouteResult(BaseModel):
    task: str
    code: str | None = None
    as_of: str | None = None
    is_panic: bool = False


def route(user_text: str, as_of: str | None = None,
          page_hint: str | None = None) -> RouteResult:
    """调 prompt router（temperature=0）；解析失败则按 page_hint 兜底。"""
    try:
        return complete_json("router", RouteResult, user_text=user_text,
                             as_of=as_of or "", page_hint=page_hint or "")
    except Exception:
        task = page_hint or "stock_outlook"
        return RouteResult(task=task, as_of=as_of)