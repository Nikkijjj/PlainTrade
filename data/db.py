"""★ agent 的唯一数据入口。

铁律
----
* as-of 一律用 publish_time / announce_date，**绝不用 ingested_at**。
* 回放模式 as_of 是「决策日」（当天不可见）；实时模式 as_of 是「当前时刻」。
* 业务代码不许写裸 SQL，只调本文件的函数。
* 重依赖（pandas）惰性导入。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from config.settings import settings

if TYPE_CHECKING:
    import pandas as pd


def _bound(as_of: str) -> str:
    """统一 as-of 上界。

    '2025-01-04'            -> '2025-01-04 00:00:00'（回放：当天公告不可见）
    '2026-11-20 15:30:00'   -> 原样（实时：此刻之前都可见）
    """
    as_of = as_of.strip()
    return as_of if len(as_of) > 10 else as_of[:10] + " 00:00:00"


@contextmanager
def connect(readonly: bool = True) -> Iterator[sqlite3.Connection]:
    """默认只读打开，防止 agent 误写。"""
    if readonly:
        conn = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def last_ingest(dataset: str) -> str | None:
    """该数据集最后一次成功抓取的时间（用于 TTL 判断）。"""
    sql = ("SELECT run_at FROM ingest_log WHERE dataset=? AND status='ok'"
           " ORDER BY id DESC LIMIT 1")
    with connect() as c:
        row = c.execute(sql, (dataset,)).fetchone()
    return row["run_at"] if row else None


def asof_docs(code: str, as_of: str, k: int = 10) -> list[dict]:
    """只返回 publish_time < as_of 的公告，按时间倒序。"""
    sql = ("SELECT art_code, code, title, notice_date, publish_time, doc_type,"
           " url, content, content_len FROM announcements"
           " WHERE code = ? AND publish_time < ? ORDER BY publish_time DESC LIMIT ?")
    with connect() as c:
        rows = c.execute(sql, (code, _bound(as_of), k)).fetchall()
    return [dict(r) for r in rows]


def asof_financials(code: str, as_of: str) -> dict[str, float]:
    """只返回 announce_date < as_of 的最近一期财务指标。"""
    sql = ("SELECT report_period, item, value FROM financials"
           " WHERE code = ? AND announce_date IS NOT NULL AND announce_date < ?"
           " ORDER BY announce_date DESC, report_period DESC")
    with connect() as c:
        rows = c.execute(sql, (code, _bound(as_of))).fetchall()
    if not rows:
        return {}
    latest = rows[0]["report_period"]
    return {r["item"]: r["value"] for r in rows if r["report_period"] == latest}


def asof_valuation(code: str, as_of: str) -> dict:
    """贵不贵：as_of 当天收盘价 + 已披露的最后一份财报，自己算 PE / PB。

    口径：PE = 总市值 / 年化净利润（年化 = 累计净利润 x 12/累计月数）；PB = 总市值 / 净资产。
    """
    from data.sources.em_finance import quarter_months
    with connect() as c:
        px = c.execute(
            "SELECT date, close FROM prices_daily WHERE code=? AND adj='qfq'"
            " AND date < ? ORDER BY date DESC LIMIT 1", (code, as_of[:10])).fetchone()
        ins = c.execute("SELECT total_shares FROM instruments WHERE code=?",
                        (code,)).fetchone()
        fin = c.execute(
            "SELECT report_period, item, value FROM financials"
            " WHERE code=? AND announce_date < ? ORDER BY announce_date DESC",
            (code, _bound(as_of))).fetchall()
    if not px or not ins or not ins["total_shares"] or not fin:
        return {}
    latest = fin[0]["report_period"]
    items = {r["item"]: r["value"] for r in fin if r["report_period"] == latest}
    mkt = float(px["close"]) * float(ins["total_shares"])
    months = quarter_months(latest) or 12
    net_profit, equity = items.get("net_profit"), items.get("total_equity")
    pe = round(mkt / (net_profit * 12 / months), 1) if net_profit and net_profit > 0 else None
    pb = round(mkt / equity, 2) if equity and equity > 0 else None
    return {"date": px["date"], "close": px["close"], "total_mv": mkt, "pe": pe,
            "pb": pb, "report_period": latest, "debt_ratio": items.get("debt_ratio")}


def series(code: str, start: str, end: str, adj: str = "hfq") -> "pd.DataFrame":
    """日线序列。adj 必须显式传（展示用 qfq，算收益用 hfq/qfq 等价）。"""
    import pandas as pd
    sql = ("SELECT date, open, high, low, close, volume, amount FROM prices_daily"
           " WHERE code = ? AND adj = ? AND date BETWEEN ? AND ? ORDER BY date")
    with connect() as c:
        rows = c.execute(sql, (code, adj, start, end)).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def trade_dates(start: str, end: str) -> list[str]:
    """交易日历 = 指数日线的日期集合，不单独维护。"""
    sql = "SELECT DISTINCT date FROM index_daily WHERE date BETWEEN ? AND ? ORDER BY date"
    with connect() as c:
        rows = c.execute(sql, (start, end)).fetchall()
    return [r["date"] for r in rows]


def search_docs(query: str, as_of: str, k: int = 10) -> list[dict]:
    """FTS5 检索（必须带 as_of 约束）。"""
    from data.text import fts_expr
    sql = ("SELECT d.doc_id, d.title,"
           " snippet(docs_fts, 4, '[', ']', '...', 12) AS snippet,"
           " bm25(docs_fts) AS score"
           " FROM docs_fts d JOIN announcements a ON a.art_code = d.doc_id"
           " WHERE docs_fts MATCH ? AND a.publish_time < ?"
           " ORDER BY score LIMIT ?")
    with connect() as c:
        rows = c.execute(sql, (fts_expr(query), _bound(as_of), k)).fetchall()
    return [dict(r) for r in rows]


def news_since(since: str, keyword: str | None = None, k: int = 20) -> list[dict]:
    """近端新闻。警告：历史决策点禁止调用（新闻只有最近 40 天）。"""
    sql = "SELECT time, title, summary, media, url FROM news WHERE time >= ?"
    args: list = [since[:10] + " 00:00:00"]
    if keyword:
        sql += " AND (title LIKE ? OR summary LIKE ?)"
        args += [f"%{keyword}%", f"%{keyword}%"]
    sql += " ORDER BY time DESC LIMIT ?"
    args.append(k)
    with connect() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]

def board_pct_changes(as_of: str, k: int = 8) -> list[dict]:
    """事件场景：as_of 当天各板块涨跌幅（按绝对值倒序）。

    取「<= as_of 的最近一个交易日」，避免周末/节假日取不到数据。
    """
    with connect() as c:
        day = c.execute("SELECT max(date) FROM board_daily WHERE date < ?",
                        (as_of[:10],)).fetchone()[0]
        if not day:
            return []
        rows = c.execute(
            "SELECT d.board_code, COALESCE(b.board_name, d.board_code) AS board_name,"
            " d.pct_chg FROM board_daily d LEFT JOIN boards b USING(board_code)"
            " WHERE d.date = ? AND d.pct_chg IS NOT NULL"
            " ORDER BY abs(d.pct_chg) DESC LIMIT ?", (day, k)).fetchall()
    return [dict(r) for r in rows]


def asof_industry(code: str) -> str | None:
    """标的所属行业（用于判断"是行业性的还是它自己的问题"）。"""
    with connect() as c:
        row = c.execute("SELECT industry FROM instruments WHERE code=?",
                        (code,)).fetchone()
    return row["industry"] if row else None
