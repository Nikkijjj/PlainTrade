"""研究层：三分析师 → 辩论 → 经理，以及取数辅助、图表数据、寒暄短路。

从 pipeline/run.py 拆出来，保持 run.py 只做编排（≤200 行）。
"""
from __future__ import annotations

from contracts.argdoc import ArgDoc, Evidence
from contracts.brief import ConfidencePlain, PlainBrief
from data import db
from observability.trace import current_run_id

_ANALYST_CN = {"fundamental_analyst": "基本面", "disclosure_analyst": "公告",
               "technical_analyst": "技术"}


def research(ctx: dict) -> ArgDoc:
    """三分析师 -> 辩论（可关）-> 经理。每个分析师失败都单独 skip。"""
    from agents.analysts.disclosure import DisclosureAnalyst
    from agents.analysts.fundamental import FundamentalAnalyst
    from agents.analysts.technical import TechnicalAnalyst
    from agents.debate import debate
    from agents.manager import decide
    from config.settings import settings

    emit = ctx.get("on_event")

    messages = []
    for a in (FundamentalAnalyst(), DisclosureAnalyst(), TechnicalAnalyst()):
        if emit:
            emit("analyst", f"分析师「{_ANALYST_CN.get(a.name, a.name)}」分析中…")
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
    if settings.debate_enabled:
        if emit:
            emit("debate", "多空正在辩论…")
        try:
            dbres = debate(claims, evidence_ids)
        except Exception:                           # noqa: BLE001  skip on fail
            dbres = None

    if emit:
        emit("manager", "经理正在汇总结论…")
    return decide(task=ctx["task"], code=ctx["code"], as_of=ctx["as_of"],
                  messages=messages, debate_result=dbres, evidence=evidence)


def indicators(code: str, as_of: str) -> dict:
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


def chart_data(spec, code: str | None, as_of: str) -> dict:
    """按 spec.data_ref 取数（渲染层不碰 DB）。"""
    if spec.data_ref.startswith("series:") and code:
        df = db.series(code, "2023-01-01", as_of[:10], adj="qfq")
        return {"dates": df["date"].tolist(), "close": df["close"].tolist()}
    if spec.data_ref == "board_pct_changes":
        rows = db.board_pct_changes(as_of, k=8)
        return {"names": [x["board_name"] for x in rows],
                "values": [x["pct_chg"] for x in rows]}
    return {}


def chit_chat_brief(user_text: str, as_of: str) -> PlainBrief:
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
