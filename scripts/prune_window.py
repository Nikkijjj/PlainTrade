"""把库裁剪到实验窗口，避免"未来数据"混进快照。

背景：开发过程中 refresh 往库里补过 2026-11 的实时数据，而实验窗口是
2023-01 ~ 2025-06。虽然 as-of 查询会挡住未来数据，但快照本身应当干净：
① 可复现（同一窗口重跑得到同一份库）；② 体积更小；③ 不会有人误用全表统计。

用法
----
python -m scripts.prune_window --start 20230101 --end 20250630
python -m scripts.prune_window --start 20230101 --end 20250630 --dry-run
"""
from __future__ import annotations

import argparse
import sys

from data import db

TABLES = (
    ("prices_daily", "date"),
    ("index_daily", "date"),
    ("board_daily", "date"),
    ("announcements", "notice_date"),
    ("news", "substr(time,1,10)"),
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20230101")
    ap.add_argument("--end", default="20250630")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lo = f"{args.start[:4]}-{args.start[4:6]}-{args.start[6:8]}"
    hi = f"{args.end[:4]}-{args.end[4:6]}-{args.end[6:8]}"
    print(f"窗口：{lo} ~ {hi}{'（dry-run，不写入）' if args.dry_run else ''}")

    total = 0
    with db.connect(readonly=args.dry_run) as c:
        for table, col in TABLES:
            n_before = c.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            out_of_range = c.execute(
                f"SELECT count(*) FROM {table} WHERE {col} < ? OR {col} > ?",
                (lo, hi)).fetchone()[0]
            if not args.dry_run and out_of_range:
                c.execute(f"DELETE FROM {table} WHERE {col} < ? OR {col} > ?", (lo, hi))
            total += out_of_range
            print(f"  {table:<15} {n_before:>6} 行，窗口外 {out_of_range:>5} 行")
        if not args.dry_run:
            c.commit()

    if not args.dry_run:
        print("\n裁剪后：")
        with db.connect() as c:
            for table, _ in TABLES:
                print(f"  {table:<15} {c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:>6} 行")
    print(f"\n{'将删除' if args.dry_run else '已删除'} {total} 行窗口外数据")
    return 0


if __name__ == "__main__":
    sys.exit(main())
