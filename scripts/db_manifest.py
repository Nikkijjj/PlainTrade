"""数据快照清单：写/校验 manifest.json。

为什么需要它
-----------
数据库是二进制，git 看不出内容。有了 manifest，任何人 clone 下来都能：
  ① 确认自己拿到的库是完整的（sha256 + 行数）
  ② 知道这份快照**缺什么**（正文/板块未补），不会误以为数据齐全
  ③ 知道实验窗口边界，不会拿窗口外的数据做统计

用法
----
python -m scripts.db_manifest --write     # 写完 data_files/manifest.json（提交它）
python -m scripts.db_manifest --verify    # 校验本地库与 manifest 是否一致
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import settings

CST = timezone(timedelta(hours=8))
MANIFEST = Path("data_files/manifest.json")
TABLES = ("instruments", "prices_daily", "index_daily", "announcements",
          "financials", "boards", "board_daily", "board_members",
          "news", "docs_fts")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(db: Path) -> dict:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    counts = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
    span = {}
    for table, col in (("prices_daily", "date"), ("index_daily", "date"),
                       ("announcements", "notice_date"), ("board_daily", "date")):
        try:
            lo, hi = c.execute(f"SELECT min({col}), max({col}) FROM {table}").fetchone()
            span[table] = [lo, hi]
        except sqlite3.Error:
            span[table] = [None, None]
    with_body = c.execute(
        "SELECT count(*) FROM announcements WHERE content_len > 0").fetchone()[0]
    c.close()

    gaps = []
    if with_body == 0:
        gaps.append("公告正文 0 条：Evidence.quote 只能用标题，保真度判定会偏宽松")
    elif with_body < counts["announcements"]:
        gaps.append(f"公告正文仅 {with_body}/{counts['announcements']} 条")
    if counts["board_daily"] == 0:
        gaps.append("板块 0 行：market_event 的板块图没数据（chart.plan 须降级为 skip）")
    if counts["news"] == 0:
        gaps.append("新闻 0 条：回放模式下正常（新闻不可回溯），live 模式会抓")

    return {
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "db_file": db.name,
        "sha256": sha256(db),
        "size_mb": round(db.stat().st_size / 1e6, 2),
        "window": {"start": "2023-01-01", "end": "2025-06-30"},
        "counts": counts,
        "date_span": span,
        "announcements_with_body": with_body,
        "known_gaps": gaps,
        "note": "这是开发期的半成品快照，数据冻结后会用同名文件覆盖并更新 sha256",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="写入 manifest.json")
    ap.add_argument("--verify", action="store_true", help="校验本地库")
    args = ap.parse_args()

    db = Path(settings.db_path)
    if not db.exists():
        print(f"找不到数据库：{db}")
        print("获取方式见 README「数据怎么拿」")
        return 1

    info = collect(db)

    if args.write:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"已写入 {MANIFEST}")
        print(f"  sha256 {info['sha256'][:16]}…  {info['size_mb']} MB")
        for t, n in info["counts"].items():
            print(f"  {t:<15} {n:>7}")
        if info["known_gaps"]:
            print("  已知缺口：")
            for g in info["known_gaps"]:
                print("   ·", g)
        return 0

    # 默认 verify
    if not MANIFEST.exists():
        print("没有 manifest.json，先跑 --write")
        return 1
    want = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = []
    if want["sha256"] != info["sha256"]:
        problems.append(f"sha256 不一致（清单 {want['sha256'][:12]}… 本地 {info['sha256'][:12]}…）")
    for t, n in want["counts"].items():
        if info["counts"].get(t) != n:
            problems.append(f"{t} 行数不一致（清单 {n}，本地 {info['counts'].get(t)}）")
    if problems:
        print("本地库与清单不一致：")
        for p in problems:
            print("  ·", p)
        print("\n如果你刚重建过库，这是正常的 —— 需要更新清单：")
        print("  python -m scripts.db_manifest --write")
        return 1
    print(f"校验通过 ✓ sha256 {info['sha256'][:16]}…")
    print(f"缺口提醒：{len(info['known_gaps'])} 项")
    for g in info["known_gaps"]:
        print("  ·", g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
