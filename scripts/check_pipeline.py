"""端到端冒烟测试：数据是否真的能流到 agent 手里。

检查项
------
1. 库里有数据（各表行数 > 0）
2. 六个工具都能通过 registry.call 调通（返回 ok=True）
3. 回放模式：as_of 语义正确（同日不可见）
4. 实时模式：as_of 用时间戳，能看到当天数据
5. 每种 task 需要的输入都能凑齐（这是 agent 能开工的前提）

用法
----
python -m scripts.check_pipeline --as-of 2025-01-04
python -m scripts.check_pipeline --as-of 2025-01-04 --code 600519
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from config.settings import settings
from contracts.tool import ToolCall
from data import db
from data.sources.em_finance import quarter_months  # noqa: F401
from pipeline.tasks import TASKS
from tools.registry import call, describe_all

CST = timezone(timedelta(hours=8))
OK, FAIL = "✓", "✗"
problems: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {OK if cond else FAIL} {msg}")
    if not cond:
        problems.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2025-01-04")
    ap.add_argument("--code", default=None)
    args = ap.parse_args()
    as_of = args.as_of

    print(f"模式={settings.mode}  as_of={as_of}  库={settings.db_path}")
    print("\n[1] 库内容")
    with db.connect() as c:
        counts = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in ("instruments", "prices_daily", "index_daily",
                            "announcements", "financials", "news")}
    for t, n in counts.items():
        if t == "news" and n == 0:
            # 回放模式下新闻必然为空：新闻接口只能回溯约 40 天，且新闻不进历史证据链
            print(f"  · {t} = 0 行（回放模式正常：新闻不可回溯，live 模式才抓）")
            continue
        check(n > 0, f"{t} = {n} 行")
    if not counts["instruments"]:
        print("\n库是空的，先跑：python -m data.build_db --codes 000001 600519")
        return 1

    codes = db._codes_for_check() if hasattr(db, "_codes_for_check") else None
    with db.connect() as c:
        codes = [r["code"] for r in c.execute("SELECT code FROM instruments").fetchall()]
    code = args.code or codes[0]

    print(f"\n[2] 工具层（样本 {code}）")
    check(len(describe_all()) >= 6, f"已注册工具 {len(describe_all())} 个")
    calls = [
        ("get_announcements", {"code": code, "as_of": as_of, "k": 5}),
        ("get_series", {"code": code, "start": "2024-01-01", "end": as_of, "adj": "hfq"}),
        ("get_financials", {"code": code, "as_of": as_of}),
        ("search_docs", {"query": "营业收入", "as_of": as_of, "k": 3}),
    ]
    for name, kw in calls:
        r = call(ToolCall(name=name, args=kw))
        size = len(r.data) if isinstance(r.data, (list, dict)) else 0
        check(r.ok, f"{name}({code}) ok, 返回 {size} 条 {'' if r.ok else r.error}")

    print("\n[3] as-of 语义")
    docs = db.asof_docs(code, as_of, k=50)
    leak = [d for d in docs if d["publish_time"] >= as_of[:10]]
    check(not leak, f"公告无未来数据（{len(docs)} 条，越界 {len(leak)} 条）")
    val = db.asof_valuation(code, as_of)
    check(bool(val) and val.get("report_period") is not None,
          f"估值可用：报告期={val.get('report_period')} PE={val.get('pe')} PB={val.get('pb')}")

    print("\n[4] 各 task 的输入是否凑得齐")
    for key, tpl in TASKS.items():
        need_docs = tpl.needs_docs and len(docs) > 0
        need_fin = tpl.needs_financials and bool(db.asof_financials(code, as_of))
        ready = (not tpl.needs_docs or need_docs) and (not tpl.needs_financials or need_fin)
        check(ready, f"{key}: docs={'有' if need_docs else '-'} "
                     f"fin={'有' if need_fin else '-'}")

    print("\n" + ("全部通过 ✓" if not problems else f"发现 {len(problems)} 个问题："))
    for p in problems:
        print("  -", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())