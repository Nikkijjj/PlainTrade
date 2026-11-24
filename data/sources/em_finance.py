"""财务数据（东财 datacenter）。实测可用。

为什么用直连接口而不是 akshare：akshare 只是它的封装，直连少一层版本依赖。

两个坑（实测踩到）
------------------
1. 东财会对同一报告期返回**追溯调整（重述）行**，NOTICE_DATE 更晚。若用 REPLACE
   就会用"事后修订版"覆盖"当时披露版"，破坏点时间语义 -> 入库侧改成首次披露优先。
2. **利润表接口的 NOTICE_DATE 不可靠**（同一报告期常给出很晚的日期）。
   同一报告期三张表同日披露，所以统一**以资产负债表的 NOTICE_DATE 为准**。
"""
from __future__ import annotations

import requests

from data.sources.base import get_json

BASE = "https://datacenter-web.eastmoney.com/api/data/v1/get"
RPT_INCOME = "RPT_DMSK_FN_INCOME"
RPT_BALANCE = "RPT_DMSK_FN_BALANCE"


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _period(report_date: str) -> str | None:
    """'2026-09-30 00:00:00' -> '2026Q3'"""
    d = (report_date or "")[:10]
    if len(d) < 10:
        return None
    q = {3: 1, 6: 2, 9: 3, 12: 4}.get(int(d[5:7]))
    return f"{d[:4]}Q{q}" if q else None


def _query(sess: requests.Session, report_name: str, code: str, page_size: int):
    js = get_json(sess, BASE, {
        "reportName": report_name, "columns": "ALL",
        "filter": f'(SECURITY_CODE="{code}")',
        "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": "REPORT_DATE", "sortTypes": "-1",
        "source": "WEB", "client": "WEB",
    }, tag="finance")
    return (js.get("result") or {}).get("data") or []


def fetch_financials(sess: requests.Session, code: str, periods: int = 20) -> list[dict]:
    """返回长表 [{report_period, announce_date, item, value, unit}]。

    announce_date 统一取资产负债表的 NOTICE_DATE（见模块注释第 2 条）。
    """
    bal = _query(sess, RPT_BALANCE, code, periods)
    notice: dict[str, str] = {}
    rows: list[dict] = []
    for r in bal:
        period = _period(r.get("REPORT_DATE"))
        ann = (r.get("NOTICE_DATE") or "")[:10]
        if not period or not ann:
            continue
        notice[period] = min(notice.get(period, ann), ann)     # 多次返回取最早
        for item, key, unit in (("total_equity", "TOTAL_EQUITY", "元"),
                                ("total_assets", "TOTAL_ASSETS", "元"),
                                ("debt_ratio", "DEBT_ASSET_RATIO", "%")):
            v = _num(r.get(key))
            if v is not None:
                rows.append({"report_period": period, "announce_date": ann,
                             "item": item, "value": v, "unit": unit})

    for r in _query(sess, RPT_INCOME, code, periods):
        period = _period(r.get("REPORT_DATE"))
        if not period:
            continue
        ann = notice.get(period) or (r.get("NOTICE_DATE") or "")[:10]
        if not ann:
            continue
        for item, key in (("revenue", "TOTAL_OPERATE_INCOME"),
                          ("net_profit", "PARENT_NETPROFIT")):
            v = _num(r.get(key))
            if v is not None:
                rows.append({"report_period": period, "announce_date": ann,
                             "item": item, "value": v, "unit": "元"})
    return rows


def quarter_months(report_period: str) -> int:
    """'2026Q3' -> 9（累计月数，用于把累计净利润年化）"""
    return {"1": 3, "2": 6, "3": 9, "4": 12}.get(report_period[-1:], 12)