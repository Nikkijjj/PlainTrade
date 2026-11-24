"""东财财经新闻（np-listapi getNewsByColumns）。实测：可翻 250 页，约回退 40 天。

警告：仅用于近端场景；历史决策点不得使用（前视偏差）。
"""
from __future__ import annotations

import time

import requests

from data.sources.base import get_json

LIST = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"


def fetch_page(sess: requests.Session, column: str = "345",
               page: int = 1, size: int = 20):
    js = get_json(sess, LIST, {
        "client": "web", "biz": "web_news_col", "column": column, "order": "1",
        "needInteractData": "0", "page_index": str(page), "page_size": str(size),
        "req_trace": str(int(time.time() * 1000)),      # 必须，缺了会返回空
    }, tag="news")
    data = js.get("data") or {}
    out = []
    for it in data.get("list") or []:
        out.append({"url": (it.get("uniqueUrl") or it.get("url") or "").strip(),
                    "time": (it.get("showTime") or "").strip(),
                    "title": (it.get("title") or "").strip(),
                    "summary": (it.get("summary") or "").strip(),
                    "media": (it.get("mediaName") or "").strip(),
                    "code": str(it.get("code") or ""),
                    "image": (it.get("image") or "").strip(),
                    "column_id": column})
    return out, int(data.get("totle_hits") or 0)