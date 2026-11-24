"""公告列表 + 正文。实测：可回溯到 2023，正文可取。按「个股 x 区间」拉。"""
from __future__ import annotations

import re

import requests

from data.sources.base import get_json

LIST = "https://np-anotice-stock.eastmoney.com/api/security/ann"
DETAIL = "https://np-cnotice-stock.eastmoney.com/api/content/ann"


def fetch_list(sess: requests.Session, *, code: str, begin: str, end: str,
               page: int = 1, size: int = 100):
    """单页公告列表。返回 (rows, total_hits)。"""
    js = get_json(sess, LIST, {
        "sr": "-1", "page_size": str(size), "page_index": str(page),
        "ann_type": "A", "client_source": "web", "f_node": "0", "s_node": "0",
        "stock_list": code, "begin_time": begin, "end_time": end,
    }, tag="notice_list")
    data = js.get("data") or {}
    out = []
    for it in data.get("list") or []:
        out.append({"art_code": it.get("art_code"),
                    "code": (it.get("codes") or [{}])[0].get("stock_code"),
                    "title": (it.get("title") or "").strip(),
                    "notice_date": (it.get("notice_date") or "")[:10],
                    "doc_type": classify(it.get("title") or ""),
                    "url": "https://data.eastmoney.com/notices/detail/%s/%s.html"
                           % (code, it.get("art_code"))})
    return out, int(data.get("totle_hits") or 0)


def fetch_all(sess: requests.Session, *, code: str, begin: str, end: str,
              size: int = 100, max_pages: int = 6) -> list[dict]:
    """翻页取全区间公告。

    坑：`totle_hits` 是区间总数，单页上限 100 —— 只取第 1 页会漏掉更早的公告
    （实测 2023-01~2025-06 每只约 150-200 条，必须翻到第 2 页）。
    """
    out: list[dict] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        rows, total = fetch_list(sess, code=code, begin=begin, end=end,
                                 page=page, size=size)
        new = [r for r in rows if r["art_code"] not in seen]
        for r in new:
            seen.add(r["art_code"])
        out.extend(new)
        # 用「本页没拿满」判断结束，不要用 totle_hits —— 实测该字段常为 0/不可靠，
        # 用它会导致只取第 1 页（每只 100 条），2023 年的公告全部漏掉。
        if not new or len(rows) < size:
            break
        if total and len(out) >= total:
            break
    return out


def fetch_content(sess: requests.Session, art_code: str) -> str:
    js = get_json(sess, DETAIL, {"art_code": art_code, "client_source": "web",
                                 "page_index": "1"}, tag="notice_detail")
    return ((js.get("data") or {}).get("notice_content") or "").strip()


def classify(title: str) -> str:
    if re.search(r"年度报告|年报", title):
        return "年报"
    if re.search(r"季度报告|季报", title):
        return "季报"
    if re.search(r"半年度报告", title):
        return "半年报"
    if re.search(r"分红|利润分配", title):
        return "分红"
    return "其他"