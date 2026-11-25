"""巨潮资讯公告接口（官方披露平台，深交所背景）。实测可用（2026-11）。

与东财的关系：东财 `np-cnotice-stock` 只给截断到 5000 字的纯文本，且约 60 次/窗口
会封 IP。巨潮给的是 **PDF**（年报全文 176k 字/143 页），不同主机、无截断。
本项目用巨潮补财报类公告正文，东财保留标题索引。

orgId 规则（实测）：**不是简单拼接**。深市主板/沪市主板多为 `gssz0`/`gssh0`+code，
但不少股票是 `990000xxxx` 或 `GDxxxx`（如美的 9900005965、宁德 GD165627）。
正确做法：拉官方列表 `szse_stock.json`（实测含全市场 6,267 条）建 code→orgId 缓存。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

QUERY = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE = "http://static.cninfo.com.cn/"
SZSE_LIST = "http://www.cninfo.com.cn/new/data/szse_stock.json"
ORGID_CACHE = Path("data_files/cninfo_orgid.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA, "Accept": "*/*", "X-Requested-With": "XMLHttpRequest",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
    })
    return s


def _load_orgid_map(sess: requests.Session) -> dict[str, str]:
    """code → orgId。优先读缓存，没有则拉官方列表（约 2MB）落缓存。"""
    if ORGID_CACHE.exists():
        return json.loads(ORGID_CACHE.read_text(encoding="utf-8"))
    r = sess.get(SZSE_LIST, timeout=90)
    r.raise_for_status()
    js = r.json()
    arr = js if isinstance(js, list) else (js.get("stockList") or js.get("data") or [])
    m = {str(it.get("code")): str(it.get("orgId"))
         for it in arr if it.get("code") and it.get("orgId")}
    ORGID_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ORGID_CACHE.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return m


def stock_id(sess: requests.Session, code: str) -> str:
    """'600519' -> '600519,gssh0600519'。orgId 从官方列表取，查不到才用拼接兜底。"""
    m = _load_orgid_map(sess)
    oid = m.get(code) or (("gssh0" if code.startswith(("6", "9")) else "gssz0") + code)
    return f"{code},{oid}"


def fetch_list(sess: requests.Session, code: str, begin: str, end: str,
               page_size: int = 30, max_pages: int = 60) -> list[dict]:
    """翻页取 code 在 [begin, end] 区间的全部公告（标题 + PDF 路径 + 时间戳）。"""
    sid = stock_id(sess, code)
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        r = sess.post(QUERY, data={
            "pageNum": str(page), "pageSize": str(page_size),
            "column": "szse", "tabName": "fulltext", "plate": "",
            "stock": sid, "searchkey": "", "secid": "",
            "category": "", "trade": "", "seDate": f"{begin}~{end}",
            "sortName": "", "sortType": "", "isHLtitle": "true",
        }, timeout=30)
        r.raise_for_status()
        js = r.json()
        total = int(js.get("totalRecordNum") or 0)
        anns = js.get("announcements") or []
        for a in anns:
            t = int(a.get("announcementTime") or 0)
            ts = time.strftime("%Y-%m-%d", time.localtime(t / 1000)) if t else ""
            out.append({"title": (a.get("announcementTitle") or "").strip(),
                        "adjunct_url": (a.get("adjunctUrl") or "").strip(),
                        "time": ts})
        if not anns or len(out) >= total:
            break
    return out


def fetch_pdf(sess: requests.Session, adjunct_url: str, timeout: int = 90) -> bytes:
    """下载 PDF。adjunct_url 形如 'finalpage/2025-04-03/1222993920.PDF'。"""
    url = adjunct_url if adjunct_url.startswith("http") else PDF_BASE + adjunct_url
    r = sess.get(url, timeout=timeout)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ValueError(f"不是 PDF：{url[:60]}（{len(r.content)} 字节）")
    return r.content
