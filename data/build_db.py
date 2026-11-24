"""建库入口：抓取 -> 清洗 -> 入 SQLite -> 建 FTS 索引 -> 记 ingest_log。

用法
----
python -m data.build_db                            # 全量（约 20 分钟）
python -m data.build_db --codes 000001 600519      # 只跑两只（联调用）
python -m data.build_db --skip announcements news   # 只更新行情与财务
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from config.settings import settings
from data import boards, db, etl, indexer
from data.sources.base import session
from observability.logger import now_iso

DEFAULT_CODES = ["000001", "600519", "600036", "000333",
                 "002415", "300750", "601318", "603259"]
DEFAULT_INDEX = {"0.399006": "创业板指", "1.000001": "上证指数"}


def init_db() -> None:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.executescript(Path("data/schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def _log(dataset: str, rows: int, lo: str, hi: str, status: str = "ok") -> None:
    with db.connect(readonly=False) as c:
        c.execute("INSERT INTO ingest_log(dataset,run_at,rows,min_date,max_date,"
                  "status,meta_json) VALUES (?,?,?,?,?,?,?)",
                  (dataset, now_iso(), rows, lo, hi, status, "{}"))
        c.commit()


def _step(name: str, fn, *args, **kwargs):
    print(f"[{now_iso()}] {name} ...", flush=True)
    rows, lo, hi = fn(*args, **kwargs)
    _log(name, len(rows), lo, hi)
    print(f"        done: {len(rows)} 行", flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", nargs="*", default=DEFAULT_CODES)
    ap.add_argument("--start", default="20230101")
    ap.add_argument("--end", default="20250630")
    ap.add_argument("--max-ann", type=int, default=0)
    ap.add_argument("--no-content", action="store_true")
    ap.add_argument("--news-pages", type=int, default=3)
    ap.add_argument("--skip", nargs="*", default=[],
                    help="跳过：instruments/prices/index/finance/announcements/news/fts")
    args = ap.parse_args()
    skip = set(args.skip)

    init_db()
    sess = session()

    if "instruments" not in skip:
        _step("instruments", etl.load_instruments, sess, args.codes)
    if "boards" not in skip:
        boards.fill_industries(sess)          # 先补行业，选板才准
        _step("boards", boards.load_boards, sess, args.start, args.end)
    if "prices" not in skip:
        _step("prices", etl.load_prices, sess, args.codes, args.start, args.end)
    if "index" not in skip:
        _step("index", etl.load_index, sess, DEFAULT_INDEX, args.start, args.end)
    if "finance" not in skip:
        _step("financials", etl.load_financials, sess, args.codes, 20)
    if "announcements" not in skip:
        _step("announcements", etl.load_announcements, sess, args.codes,
              args.start, args.end, args.max_ann, not args.no_content)
    if "news" not in skip:
        _step("news", etl.load_news, sess, args.news_pages)
    if "fts" not in skip:
        _step("fts", lambda: ([{}] * indexer.build_fts(), args.start, args.end))

    with db.connect() as c:
        for t in ("instruments", "prices_daily", "index_daily", "boards", "board_daily",
                  "announcements", "financials", "news"):
            n = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"  {t:<15} {n:>7} 行")
    print("建库完成")


if __name__ == "__main__":
    main()