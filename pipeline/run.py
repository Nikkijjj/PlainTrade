"""唯一编排入口：user_text -> PlainBrief。

依赖方向：只 import agents/adapt/guardrails/data，不许被它们 import。
as_of 在入口固定一次，全链路只传不重取。
"""
from __future__ import annotations

from adapt import chart, summarize
from agents.router import route
from config.settings import settings
from data import db, refresh
from observability.trace import new_run_id, span
from pipeline.tasks import TASKS


def run(user_text: str, as_of: str):
    """一次完整请求。live 模式会在取数前按 TTL 增量刷新（唯一碰网络的地方）。"""
    new_run_id()

    with span("refresh"):
        if settings.mode == "live":
            refresh.ensure_fresh(["news", "prices", "index"], verbose=False)

    with span("router"):
        r = route(user_text, as_of=as_of)
    tpl = TASKS[r.task]

    with span("fetch"):
        docs = db.asof_docs(r.code, as_of, k=10) if (tpl.needs_docs and r.code) else []
        fin = (db.asof_financials(r.code, as_of)
               if (tpl.needs_financials and r.code) else {})
        val = db.asof_valuation(r.code, as_of) if r.code else {}

    with span("analysts"):
        argdoc = _research({"task": r.task, "code": r.code, "as_of": as_of,
                            "docs": docs, "financials": fin, "valuation": val,
                            "evidence_ids": [d.get("art_code") for d in docs]})

    with span("summarize"):
        one_liner, stance_plain, conf = summarize.summarize(argdoc)

    with span("chart"):
        spec = chart.plan(argdoc) if settings.chart_enabled else None

    # 组装 PlainBrief 时**必须**做这一步，否则 charts[].image_path 永远是空、前端一张图都没有
    # （这是上线前审计发现的历史漏洞，别忘）：
    #
    #   from adapt.render import render
    #   if spec and spec.decision.value == "emit":
    #       png = render(spec, chart_data, Path("data_files/charts"))
    #       block = ChartBlock(spec=spec, image_path=str(png))
    #   else:
    #       block = ChartBlock(spec=spec, image_path="")
    #
    # chart_data 按 spec.data_ref 从 db.series() / db.board_pct_changes() 取。
    raise NotImplementedError("TODO(B): 组装 PlainBrief（依赖 manager.decide 先返回 ArgDoc）")


def _research(ctx: dict):
    """三分析师 -> 辩论（可用 settings.debate_enabled 关闭）-> 经理。"""
    raise NotImplementedError("TODO(B)")