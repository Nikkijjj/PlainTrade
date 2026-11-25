"""唯一编排入口：user_text -> PlainBrief。

依赖方向：只 import agents/adapt/guardrails/data，不许被它们 import。
as_of 在入口固定一次，全链路只传不重取。

D-03：链路首次打通。质量可以差，但不能抛异常；任一 node 失败按 graph.py on_fail 降级。
"""
from __future__ import annotations

from pathlib import Path

from adapt import chart, render, summarize
from agents.router import route
from config.settings import settings
from contracts.argdoc import ArgDoc, Stance
from contracts.brief import ChartBlock, ConfidencePlain, PlainBrief, WhyPoint
from data import db, refresh
from guardrails.escalation import check as escalation_check
from observability.trace import current_run_id, new_run_id, span
from pipeline.tasks import TASKS


def run(user_text: str, as_of: str) -> PlainBrief:
    """一次完整请求。live 模式会在取数前按 TTL 增量刷新（唯一碰网络的地方）。"""
    new_run_id()

    with span("refresh"):
        if settings.mode == "live":
            refresh.ensure_fresh(["news", "prices", "index"], verbose=False)

    with span("router"):
        r = route(user_text, as_of=as_of)
    tpl = TASKS.get(r.task) or TASKS["stock_outlook"]

    # chit_chat 短路：寒暄/通用知识，不取数、不调分析师（只做一次轻量 LLM）
    if r.task == "chit_chat":
        return _chit_chat_brief(user_text, as_of)

    with span("fetch"):
        docs = db.asof_docs(r.code, as_of, k=10) if (tpl.needs_docs and r.code) else []
        fin = (db.asof_financials(r.code, as_of)
               if (tpl.needs_financials and r.code) else {})
        val = db.asof_valuation(r.code, as_of) if r.code else {}
        indicators = _indicators(r.code, as_of) if r.code else {}

    # analysts（skip on fail）→ debate（skip）→ manager（no_view 兜底）
    try:
        with span("analysts"):
            argdoc = _research({"task": r.task, "code": r.code, "as_of": as_of,
                                "docs": docs, "financials": fin, "valuation": val,
                                "indicators": indicators,
                                "evidence_ids": [d["art_code"] for d in docs]})
    except Exception as e:                          # noqa: BLE001
        argdoc = ArgDoc(task=r.task, code=r.code, as_of=as_of,
                        stance=Stance.NO_VIEW, confidence=0.0,
                        invalidation_conditions=["出现可验证的新证据后，重新评估"],
                        information_gaps=[f"研究链路失败：{type(e).__name__}: {e}"])

    with span("summarize"):
        one_liner, stance_plain, conf = summarize.summarize(argdoc)

    spec = None
    with span("chart"):
        spec = chart.plan(argdoc) if settings.chart_enabled else None

    blocks: list[ChartBlock] = []
    if spec:
        with span("render"):
            if spec.decision.value == "emit":
                try:
                    png = render.render(spec, _chart_data(spec, r.code, as_of),
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


def _research(ctx: dict) -> ArgDoc:
    """三分析师 -> 辩论（可关）-> 经理。每个分析师失败都单独 skip。"""
    from agents.analysts.disclosure import DisclosureAnalyst
    from agents.analysts.fundamental import FundamentalAnalyst
    from agents.analysts.technical import TechnicalAnalyst
    from agents.debate import debate
    from agents.manager import decide
    from contracts.argdoc import Evidence

    messages = []
    for a in (FundamentalAnalyst(), DisclosureAnalyst(), TechnicalAnalyst()):
        try:
            messages.append(a.run(ctx))
        except Exception:                           # noqa: BLE001  skip on fail
            pass

    evidence: list[Evidence] = []
    for d in ctx.get("docs", []):
        evidence.append(Evidence(
            id=d["art_code"], source=d["title"], doc_type="announcement",
            publish_time=d["publish_time"],
            quote=(d.get("content") or d["title"])[:200],
            url=d.get("url", "") or ""))
    val = ctx.get("valuation") or {}
    if val:
        evidence.append(Evidence(
            id="valuation", source="自算估值", doc_type="market_data",
            publish_time=val.get("date", ctx["as_of"][:10]),
            quote=f"PE={val.get('pe')}, PB={val.get('pb')}, 报告期={val.get('report_period')}"))

    claims = [c for m in messages for c in m.claims]
    evidence_ids = [e.id for e in evidence]
    dbres = None
    try:
        if settings.debate_enabled:
            dbres = debate(claims, evidence_ids)
    except Exception:                               # noqa: BLE001  skip on fail
        dbres = None

    return decide(task=ctx["task"], code=ctx["code"], as_of=ctx["as_of"],
                  messages=messages, debate_result=dbres, evidence=evidence)


def _indicators(code: str, as_of: str) -> dict:
    """技术指标：代码算好喂给分析师，LLM 不算数。"""
    df = db.series(code, "2023-01-01", as_of[:10], adj="hfq")
    if df.empty:
        return {}
    closes = df["close"].tolist()
    dates = df["date"].tolist()
    last = closes[-1]
    ma20 = round(sum(closes[-20:]) / min(20, len(closes)), 2) if closes else None
    ret_20d = round((last / closes[-21] - 1) * 100, 2) if len(closes) > 20 else None
    peak, mdd = -float("inf"), 0.0
    for c in closes:
        peak = max(peak, c)
        if peak:
            mdd = min(mdd, (c - peak) / peak * 100)
    return {"date": dates[-1], "close": last, "ma20": ma20,
            "ret_20d_pct": ret_20d, "max_drawdown_1y_pct": round(mdd, 2)}


def _chart_data(spec, code: str | None, as_of: str) -> dict:
    """按 spec.data_ref 取数（渲染层不碰 DB）。"""
    if spec.data_ref.startswith("series:") and code:
        df = db.series(code, "2023-01-01", as_of[:10], adj="qfq")
        return {"dates": df["date"].tolist(), "close": df["close"].tolist()}
    if spec.data_ref == "board_pct_changes":
        rows = db.board_pct_changes(as_of, k=8)
        return {"names": [x["board_name"] for x in rows],
                "values": [x["pct_chg"] for x in rows]}
    return {}


def _chit_chat_brief(user_text: str, as_of: str) -> PlainBrief:
    """寒暄/常识走轻量分支：一次 LLM 按内容回一句，失败落兜底话术。"""
    from pydantic import BaseModel
    from llm.structured import complete_json

    class _Chat(BaseModel):
        one_liner: str = ""

    default = "我是 PlainTrade，帮你把市场、个股、怎么分配钱讲明白；我不荐股、不给买卖建议。"
    try:
        chat = complete_json("chit_chat", _Chat, user_text=user_text)
        one_liner = chat.one_liner or default
    except Exception:                               # noqa: BLE001
        one_liner = default
    return PlainBrief(
        task="chit_chat",
        one_liner=one_liner,
        stance_plain="",
        confidence_plain=ConfidencePlain(value="", anchor=""),
        what_you_should_not_do=[],
        audit={"run_id": current_run_id(), "mode": "chit_chat", "as_of": as_of},
    )
