"""唯一编排入口：user_text -> PlainBrief。

依赖方向：只 import agents/adapt/guardrails/data，不许被它们 import。
as_of 在入口固定一次，全链路只传不重取。

D-03：链路首次打通。质量可以差，但不能抛异常；任一 node 失败按 graph.py on_fail 降级。
流式：run(..., on_event=cb) 会在每个阶段回调 cb({"type":"stage","stage":..,"label":..})。
"""
from __future__ import annotations

from pathlib import Path

from adapt import chart, render, summarize
from agents.router import route
from config.settings import settings
from contracts.argdoc import ArgDoc, Stance
from contracts.brief import ChartBlock, PlainBrief, WhyPoint
from data import db, refresh
from guardrails.escalation import check as escalation_check
from observability.trace import current_run_id, new_run_id, span
from pipeline.research import chart_data, chit_chat_brief, indicators, research
from pipeline.tasks import TASKS


def run(user_text: str, as_of: str, on_event=None) -> PlainBrief:
    """一次完整请求。live 模式会在取数前按 TTL 增量刷新（唯一碰网络的地方）。"""
    def emit(stage: str, label: str) -> None:
        if on_event:
            on_event({"type": "stage", "stage": stage, "label": label})

    new_run_id()
    emit("router", "正在理解你的问题…")

    with span("refresh"):
        if settings.mode == "live":
            refresh.ensure_fresh(["news", "prices", "index"], verbose=False)

    with span("router"):
        r = route(user_text, as_of=as_of)
    tpl = TASKS.get(r.task) or TASKS["stock_outlook"]

    # chit_chat 短路：寒暄/通用知识，不取数、不调分析师（只做一次轻量 LLM）
    if r.task == "chit_chat":
        emit("reply", "正在回复…")
        return chit_chat_brief(user_text, as_of)

    emit("fetch", "正在查数据…")
    with span("fetch"):
        docs = db.asof_docs(r.code, as_of, k=10) if (tpl.needs_docs and r.code) else []
        fin = (db.asof_financials(r.code, as_of)
               if (tpl.needs_financials and r.code) else {})
        val = db.asof_valuation(r.code, as_of) if r.code else {}
        ind = indicators(r.code, as_of) if r.code else {}

    # analysts（skip on fail）→ debate（skip）→ manager（no_view 兜底）
    emit("analysts", "三个分析师正在分析…")
    try:
        with span("analysts"):
            argdoc = research({"task": r.task, "code": r.code, "as_of": as_of,
                               "docs": docs, "financials": fin, "valuation": val,
                               "indicators": ind,
                               "evidence_ids": [d["art_code"] for d in docs],
                               "on_event": emit})
    except Exception as e:                          # noqa: BLE001
        argdoc = ArgDoc(task=r.task, code=r.code, as_of=as_of,
                        stance=Stance.NO_VIEW, confidence=0.0,
                        invalidation_conditions=["出现可验证的新证据后，重新评估"],
                        information_gaps=[f"研究链路失败：{type(e).__name__}: {e}"])

    emit("summarize", "正在组织语言…")
    with span("summarize"):
        one_liner, stance_plain, conf = summarize.summarize(argdoc)

    emit("chart", "正在生成图表…")
    spec = None
    with span("chart"):
        spec = chart.plan(argdoc) if settings.chart_enabled else None

    blocks: list[ChartBlock] = []
    if spec:
        with span("render"):
            if spec.decision.value == "emit":
                try:
                    png = render.render(spec, chart_data(spec, r.code, as_of),
                                        Path("data_files/charts"))
                    blocks.append(ChartBlock(spec=spec, image_path=str(png)))
                except Exception:                   # noqa: BLE001  出图失败=无图，不崩
                    blocks.append(ChartBlock(spec=spec, image_path=""))
            else:
                blocks.append(ChartBlock(spec=spec, image_path=""))

    # 越界拦截（轻量：命中则明确拒答 + 提醒）
    escalated = escalation_check(user_text)
    not_do = ["这不是让你买或卖。"]
    if escalated:
        not_do.append("你问的属于买卖操作，我给不出不越界的答案，判断留给你。")

    return PlainBrief(
        task=r.task,
        one_liner=one_liner,
        stance_plain=stance_plain,
        confidence_plain=conf,
        why=[WhyPoint(point=c.text, evidence=c.evidence) for c in argdoc.claims[:3]],
        charts=blocks,
        what_would_change_our_mind=argdoc.invalidation_conditions,
        what_you_should_not_do=not_do,
        glossary=[],
        citations=[e.source for e in argdoc.evidence],
        audit={"run_id": current_run_id(), "mode": settings.mode, "as_of": as_of,
               "task": r.task, "stance": argdoc.stance.value,
               "claims": len(argdoc.claims), "evidence": len(argdoc.evidence),
               "escalation_hits": escalated},
    )
