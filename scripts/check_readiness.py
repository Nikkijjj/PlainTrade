"""数据就绪度探针：对每个 agent 模块，打印它实际能拿到的数据。

用来回答"现在的库够不够 agent 开发"，而不是靠猜。
用法：python -m scripts.check_readiness --as-of 2025-01-04 --code 600519
"""
from __future__ import annotations

import argparse
import sys

from data import db

OK, PART, NO = "✓", "△", "✗"


def line(flag: str, module: str, need: str, got: str) -> None:
    print(f"  {flag} {module:<22} {need:<26} {got}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2025-01-04")
    ap.add_argument("--code", default="600519")
    args = ap.parse_args()
    as_of, code = args.as_of, args.code

    print(f"数据就绪度：code={code} as_of={as_of}\n")

    # ── 逐个模块看它要什么、现在有什么 ─────────────────
    print("[个股场景 stock_outlook]")

    docs = db.asof_docs(code, as_of, k=10)
    with_body = [d for d in docs if (d.get("content_len") or 0) > 0]
    flag = OK if with_body else (PART if docs else NO)
    line(flag, "公告分析师", "公告标题 + 正文", f"{len(docs)} 条标题，{len(with_body)} 条有正文")

    fin = db.asof_financials(code, as_of)
    line(OK if fin else NO, "基本面分析师", "已披露财务指标",
         f"{len(fin)} 个指标（{sorted(fin)[:3]}…）" if fin else "无")

    val = db.asof_valuation(code, as_of)
    line(OK if val.get("pe") else NO, "估值（PE/PB）", "qfq 收盘 + 总股本 + 财务",
         f"报告期 {val.get('report_period')}，PE {val.get('pe')}，PB {val.get('pb')}")

    s = db.series(code, "2024-01-01", as_of, "qfq")
    line(OK if len(s) >= 20 else NO, "技术分析师", "≥20 日 OHLCV",
         f"{len(s)} 个交易日（够画 K 线/均线/回撤）")

    hits = db.search_docs("年度报告", as_of, k=5)
    line(OK if hits else NO, "检索（search_docs）", "FTS 索引",
         f"命中 {len(hits)} 条（正文缺失，索引的是标题）")

    print("\n[事件场景 market_event]")
    idx = db.trade_dates("2024-12-25", as_of)
    line(OK if idx else NO, "指数跌幅", "index_daily",
         f"区间 {len(idx)} 个交易日")

    board = db.board_pct_changes(as_of, k=8)
    line(OK if board else NO, "板块涨跌幅", "board_daily",
         f"{len(board)} 个板块" if board else "0 —— board_daily 为空（待补）")

    news = db.news_since("2024-12-01", k=5)
    line(OK if news else PART, "近端新闻", "news（仅 live）",
         f"{len(news)} 条" if news else "0 —— 回放模式应为空")

    print("\n[钱怎么放 allocation_literacy]")
    line(OK, "分配原则 + 示例", "不需要库", "纯规则 + 示例，无数据依赖")

    # ── 结论 ─────────────────────────────────────────
    print("\n影响判断：")
    gaps = []
    if not with_body:
        gaps.append("正文缺失 → Evidence.quote 只能用标题，保真度判定(fidelity)会偏宽松")
    if not board:
        gaps.append("板块缺失 → market_event 的归因图出不来（其余不受影响）")
    if not news:
        gaps.append("新闻为空 → 事件场景只能讲指数与板块，live 模式才补")

    if not gaps:
        print("  数据齐备，无阻塞。")
    for g in gaps:
        print("  ·", g)

    print("\n对并行的结论：")
    print("  B（llm/agents/pipeline）：代码路径不依赖正文与板块，**可立即开工**")
    print("  C（adapt/ui）           ：吃 fixtures 与 ArgDoc，**可立即开工**")
    print("  A（数据/eval）          ：补正文与板块不阻塞任何人；评估指标里")
    print("                            「失真率」需要 quote，建议正文补到 >70% 再定稿数字")
    return 0


if __name__ == "__main__":
    sys.exit(main())
