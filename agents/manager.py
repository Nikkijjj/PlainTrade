"""研究经理：唯一有权输出 stance 的 agent，汇总成 ArgDoc。

职责：把三个分析师的 claim + 多空辩论合成一份带证据的结论。

关键设计（防编造）：
  * `evidence` 由代码从研究层注入（LLM 不输出证据，只输出"思考"），
    这样证据的 publish_time / quote / url 永远是研究层算好的，不会被模型编。
  * LLM 挂了也降级 no_view，不抛异常（manager 节点 abort 只在代码级 bug 时触发）。
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from agents.debate import DebateResult
from contracts.argdoc import (ArgDoc, Claim, Evidence, ExplanationStatus, Stance)
from contracts.message import AgentMessage
from llm.structured import complete_json


class _Draft(BaseModel):
    """LLM 只输出"思考"，evidence 由代码注入。"""
    stance: Stance = Stance.NO_VIEW
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    claims: list[Claim] = Field(default_factory=list)
    counter_arguments: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    explanation_status: ExplanationStatus = ExplanationStatus.NOT_APPLICABLE


def _horizon(task: str) -> str:
    return "1w" if task == "market_event" else "4w"


def _as_evidence(ev: list) -> list[Evidence]:
    """兼容 dict 与 Evidence，统一成 Evidence。"""
    out: list[Evidence] = []
    for e in ev or []:
        out.append(e if isinstance(e, Evidence) else Evidence(**e))
    return out


def _no_view(task: str, code: str | None, as_of: str,
             evidence: list[Evidence], gaps: list[str]) -> ArgDoc:
    status = (ExplanationStatus.UNKNOWN if task == "market_event"
              else ExplanationStatus.NOT_APPLICABLE)
    return ArgDoc(
        task=task, code=code, as_of=as_of, horizon=_horizon(task),
        stance=Stance.NO_VIEW, confidence=0.0,
        claims=[], counter_arguments=[],
        invalidation_conditions=["出现可验证的新证据后，重新评估"],
        information_gaps=list(gaps),
        explanation_status=status, evidence=evidence,
        audit={"mode": "no_view_fallback", "gap": "; ".join(gaps)[:120]},
    )


def _render_messages(messages: list[AgentMessage]) -> str:
    return json.dumps(
        [{"sender": m.sender,
          "claims": [c.model_dump() for c in m.claims]} for m in messages],
        ensure_ascii=False, indent=2)


def _render_debate(d: DebateResult | None) -> str:
    d = d or DebateResult()
    return json.dumps({"bull": d.bull, "bear": d.bear,
                       "invalidation_conditions": d.invalidation_conditions},
                      ensure_ascii=False, indent=2)


def _render_evidence(ev: list[Evidence]) -> str:
    return json.dumps(
        [{"id": e.id, "source": e.source, "publish_time": e.publish_time,
          "quote": e.quote[:120]} for e in ev],
        ensure_ascii=False, indent=2)


def decide(*, task: str, code: str | None, as_of: str,
           messages: list[AgentMessage], debate_result: DebateResult | None,
           evidence: list[Evidence]) -> ArgDoc:
    """汇总成 ArgDoc。

    硬规则：证据不足 → no_view；LLM 失败 → no_view（不抛）；去幻觉；
    claim 为空或没有失效条件 → 不能有明确 stance。
    """
    ev = [e for e in _as_evidence(evidence) if e.publish_time[:10] < as_of[:10]]
    all_claims = [c for m in (messages or []) for c in m.claims]

    # 证据不足（没证据 / 分析师没结论）→ 直接 no_view，不调 LLM
    if not ev or not all_claims:
        return _no_view(task, code, as_of, ev,
                        ["证据不足" if not ev else "分析师未产出有效结论"])

    try:
        draft = complete_json(
            "manager", _Draft,
            task=task, code=code or "", as_of=as_of,
            claims=_render_messages(messages),
            debate=_render_debate(debate_result),
            evidence=_render_evidence(ev))
    except Exception as e:                          # noqa: BLE001
        return _no_view(task, code, as_of, ev, [f"经理汇总失败：{e}"])

    argdoc = ArgDoc(
        task=task, code=code, as_of=as_of, horizon=_horizon(task),
        stance=draft.stance, confidence=draft.confidence,
        claims=draft.claims,
        counter_arguments=draft.counter_arguments,
        invalidation_conditions=draft.invalidation_conditions,
        information_gaps=draft.information_gaps,
        explanation_status=draft.explanation_status,
        evidence=ev,
        audit={"mode": "manager", "claim_in": len(all_claims),
               "claim_out": len(draft.claims)},
    )

    # 去幻觉：引用不存在证据的 claim 整条丢
    dangling = set(argdoc.dangling_evidence())
    if dangling:
        argdoc.claims = [c for c in argdoc.claims if not set(c.evidence) & dangling]

    # 后置：没有有效 claim / 没有失效条件 → 不能有明确 stance
    if not argdoc.claims or not argdoc.invalidation_conditions:
        argdoc.stance = Stance.NO_VIEW
        argdoc.confidence = 0.0
    return argdoc
