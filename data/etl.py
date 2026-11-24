"""按数据集装载：只做「取数 -> 清洗 -> 写库」，由 build_db.py 调度。

每个 loader 返回 (rows, min_date, max_date)，供 ingest_log 记账。

关于公告正文（实测坑）
--------------------
东财正文接口 `np-cnotice-stock/api/content/ann` 连续请求约 50 次后会开始
`RemoteDisconnected`（IP 级限流），此时**连之前成功过的公告也取不到**。
所以策略是：
  * 标题/日期/类型：一次列表请求拿 100 条，稳定；
  * 正文：单独用可断点续传的 `scripts/fill_content.py` 慢慢补；
  * 本模块遇到连续失败会自动降级为"只入库标题"，不拖垮整条管线。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from data import db
from data.sources import em_finance, em_news, em_notice, em_quote

CST = timezone(timedelta(hours=8))
DELAY = 0.35          # 限速：不要调小
CONTENT_DELAY = 1.0   # 正文接口更敏感，单独放慢
MAX_CONSECUTIVE_FAIL = 5


def _now() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(CST).date().isoformat()


def load_instruments(sess, codes: list[str]):
    out = []
    with db.connect(readonly=False) as c:
        for code in codes:
            m = em_quote.fetch_meta(sess, code)
            c.execute(
                "INSERT OR REPLACE INTO instruments"
                "(code,name,board,industry,total_shares,shares_asof,updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (m["code"], m["name"], None, m.get("industry"),
                 m["total_shares"], _today(), _now()))
            out.append(m)
            time.sleep(DELAY)
        c.commit()
    return out, "", ""


def load_prices(sess, codes: list[str], start: str, end: str):
    out = []
    with db.connect(readonly=False) as c:
        for code in codes:
            for adj in ("hfq", "qfq"):
                rows = em_quote.fetch_kline(sess, em_quote.secid_of(code), start, end, adj)
                c.executemany(
                    "INSERT OR REPLACE INTO prices_daily"
                    "(code,date,adj,open,high,low,close,volume,amount)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    [(code, r["date"], adj, r["open"], r["high"], r["low"],
                      r["close"], r["volume"], r["amount"]) for r in rows])
                out.extend(rows)
                time.sleep(DELAY)
        c.commit()
    return out, start, end


def load_index(sess, secids: dict[str, str], start: str, end: str):
    out = []
    with db.connect(readonly=False) as c:
        for secid, name in secids.items():
            rows = em_quote.fetch_kline(sess, secid, start, end, "none")
            prev = None
            for r in rows:
                pct = None if prev in (None, 0) else round((r["close"] / prev - 1) * 100, 2)
                c.execute(
                    "INSERT OR REPLACE INTO index_daily"
                    "(secid,name,date,close,pct_chg,amount) VALUES (?,?,?,?,?,?)",
                    (secid, name, r["date"], r["close"], pct, r["amount"]))
                prev = r["close"]
            out.extend(rows)
            time.sleep(DELAY)
        c.commit()
    return out, start, end


def load_financials(sess, codes: list[str], periods: int = 20):
    """财务长表入库。

    关键：东财会对同一报告期返回**追溯调整（重述）行**，其 NOTICE_DATE 更晚。
    若用 REPLACE，就会用"事后修订版"覆盖"当时披露版"，破坏点时间语义。
    所以这里按 announce_date **升序**写入 + INSERT OR IGNORE => 首次披露优先。
    """
    out = []
    with db.connect(readonly=False) as c:
        for code in codes:
            rows = em_finance.fetch_financials(sess, code, periods)
            clean = [r for r in rows if r["announce_date"]
                     and r["announce_date"] >= _report_date(r["report_period"])]
            clean.sort(key=lambda r: r["announce_date"])
            c.executemany(
                "INSERT OR IGNORE INTO financials"
                "(code,report_period,announce_date,item,value,unit)"
                " VALUES (?,?,?,?,?,?)",
                [(code, r["report_period"], r["announce_date"], r["item"],
                  r["value"], r["unit"]) for r in clean])
            out.extend(clean)
            c.commit()
            time.sleep(DELAY)
    return out, "", ""


def _report_date(period: str) -> str:
    """'2024Q3' -> '2024-09-30'（校验披露日不早于报告期）"""
    m = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}
    return f"{period[:4]}-{m.get(period[-1:], '12-31')}"


def load_announcements(sess, codes: list[str], start: str, end: str,
                       max_per_code: int = 0, with_content: bool = True,
                       content_delay: float = CONTENT_DELAY):
    """标题全量入库；正文能拿多少拿多少，连续失败则降级为只存标题。"""
    out = []
    content_off = not with_content
    consecutive_fail = 0
    saved = 0
    with db.connect(readonly=False) as c:
        for code in codes:
            rows = em_notice.fetch_all(sess, code=code, begin=start, end=end)
            if max_per_code:
                rows = rows[:max_per_code]
            for r in rows:
                content, clen = "", 0
                if not content_off:
                    try:
                        content = em_notice.fetch_content(sess, r["art_code"])
                        clen = len(content)
                        consecutive_fail = 0
                    except Exception:                     # noqa: BLE001
                        consecutive_fail += 1
                        if consecutive_fail >= MAX_CONSECUTIVE_FAIL:
                            content_off = True
                            print("        正文接口被限流，改为只入库标题"
                                  "（稍后跑 scripts/fill_content.py 补）", flush=True)
                    time.sleep(content_delay)
                if clen:
                    saved += 1
                # 关键：不能用 INSERT OR REPLACE —— 它会把之前已抓到的正文冲成空串
                # （实测 --no-content 重跑一次，38 条正文全被清掉）。
                c.execute(
                    "INSERT INTO announcements"
                    "(art_code,code,title,notice_date,publish_time,doc_type,url,"
                    " content,content_len,ingested_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(art_code) DO UPDATE SET"
                    " title=excluded.title, notice_date=excluded.notice_date,"
                    " publish_time=excluded.publish_time, doc_type=excluded.doc_type,"
                    " url=excluded.url, ingested_at=excluded.ingested_at,"
                    " content=CASE WHEN excluded.content_len>0 THEN excluded.content"
                    "              ELSE announcements.content END,"
                    " content_len=CASE WHEN excluded.content_len>0"
                    "              THEN excluded.content_len"
                    "              ELSE announcements.content_len END",
                    (r["art_code"], code, r["title"], r["notice_date"],
                     r["notice_date"] + " 23:59:59", r["doc_type"], r["url"],
                     content, clen, _now()))
                out.append(r)
            c.commit()
            time.sleep(DELAY)
    if with_content:
        print(f"        正文成功 {saved}/{len(out)} 篇", flush=True)
    return out, start, end


def load_news(sess, pages: int = 3, column: str = "345"):
    out = []
    with db.connect(readonly=False) as c:
        for page in range(1, pages + 1):
            rows, _total = em_news.fetch_page(sess, column=column, page=page)
            for r in rows:
                c.execute(
                    "INSERT OR IGNORE INTO news"
                    "(url,time,title,summary,media,code,image,column_id,ingested_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (r["url"], r["time"], r["title"], r["summary"], r["media"],
                     None, r["image"], r["column_id"], _now()))
            out.extend(rows)
            c.commit()
            time.sleep(DELAY)
    return out, "", ""
