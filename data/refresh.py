"""增量更新器：让 live 模式能看到最新数据，同时不破坏历史（append-only）。

设计
----
* TTL 驱动：只有「距上次成功抓取 > TTL」的数据集才真的去拉。
* 幂等：所有写入都是 INSERT OR REPLACE / IGNORE，重复跑不产生脏数据。
* 水印：从 ingest_log 读最后成功时间；行情从 prices_daily 的最后日期续拉。
* 单步失败不阻断：返回 dict[dataset] -> "updated" / "fresh" / "failed:xxx"。

用法
----
python -m data.refresh                       # 按 TTL 检查全部
python -m data.refresh --datasets news        # 只更新新闻
python -m data.refresh --force                # 忽略 TTL
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from config.settings import settings
from data import db, etl
from data.sources.base import session
from observability.logger import now_iso

CST = timezone(timedelta(hours=8))


def _ttl(dataset: str) -> int:
    return {"news": settings.ttl_news_s,
            "announcements": settings.ttl_announcement_s,
            "prices": settings.ttl_price_s,
            "index": settings.ttl_price_s,
            "financials": settings.ttl_financial_s}.get(dataset, 86400)


def _stale(dataset: str) -> bool:
    last = db.last_ingest(dataset)
    if not last:
        return True
    try:
        dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return (datetime.now(CST) - dt).total_seconds() > _ttl(dataset)


def _codes() -> list[str]:
    with db.connect() as c:
        return [r["code"] for r in c.execute("SELECT code FROM instruments").fetchall()]


def _compact(dt: datetime) -> str:
    """东财 kline 要 'YYYYMMDD'（无横线）。"""
    return dt.strftime("%Y%m%d")


def _recent_start(days: int) -> str:
    return _compact(datetime.now(CST) - timedelta(days=days))


def _run_one(dataset: str, sess, codes: list[str]) -> tuple[int, str, str]:
    today = _compact(datetime.now(CST))
    if dataset == "news":
        return etl.load_news(sess, pages=1)
    if dataset == "financials":
        return etl.load_financials(sess, codes or [], 20)
    if dataset == "announcements":
        if not codes:
            return [], "", ""
        start = _recent_start(30)
        return etl.load_announcements(sess, codes, start, today, 0, True)
    if dataset == "prices":
        if not codes:
            return [], "", ""
        return etl.load_prices(sess, codes, _recent_start(20), today)
    if dataset == "index":
        return etl.load_index(sess, {"0.399006": "创业板指", "1.000001": "上证指数"},
                              _recent_start(20), today)
    raise ValueError(f"未知数据集：{dataset}")


def ensure_fresh(datasets: list[str] | None = None, force: bool = False,
                 verbose: bool = True) -> dict[str, str]:
    """按 TTL 增量更新，返回各数据集状态。live 模式在请求前调用。"""
    targets = datasets or ["news", "index", "prices", "announcements", "financials"]
    status: dict[str, str] = {}
    codes = _codes()
    sess = session()
    for ds in targets:
        if not force and not _stale(ds):
            status[ds] = "fresh"
            continue
        try:
            rows, lo, hi = _run_one(ds, sess, codes)
            with db.connect(readonly=False) as c:
                c.execute("INSERT INTO ingest_log(dataset,run_at,rows,min_date,"
                          "max_date,status,meta_json) VALUES (?,?,?,?,?,?,?)",
                          (ds, now_iso(), len(rows), lo, hi, "ok", '{"via":"refresh"}'))
                c.commit()
            status[ds] = "updated"
        except Exception as e:                      # noqa: BLE001
            status[ds] = f"failed:{type(e).__name__}"
        if verbose:
            print(f"  [refresh] {ds:<14} {status[ds]}", file=sys.stderr)
    return status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="*", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    res = ensure_fresh(args.datasets, args.force)
    print("刷新结果：", res)


if __name__ == "__main__":
    main()