"""契约自检：字段完整性 + 校验规则真的会报错。用法：python -m scripts.check_contracts"""
from __future__ import annotations

import sys

from contracts.argdoc import ArgDoc, Evidence
from contracts.chart import ChartSpec
from contracts.message import AgentMessage
from contracts.argdoc import Claim


def main() -> int:
    problems: list[str] = []

    # 1) 字段完整性
    need = {
        "ArgDoc": ("task", "code", "as_of", "horizon", "stance", "confidence", "claims",
                   "counter_arguments", "invalidation_conditions", "information_gaps",
                   "explanation_status", "evidence", "audit"),
        "ChartSpec": ("decision", "need_type", "chart_type", "data_ref", "annotations",
                      "caption", "reason"),
        "AgentMessage": ("sender", "role", "task", "code", "as_of", "claims",
                         "evidence_used", "notes", "meta"),
    }
    from contracts import chart as chart_mod, message as msg_mod
    for cls, fields in ((ArgDoc, need["ArgDoc"]), (ChartSpec, need["ChartSpec"]),
                        (AgentMessage, need["AgentMessage"])):
        have = set(cls.model_fields)
        for f in fields:
            if f not in have:
                problems.append(f"{cls.__name__} 缺字段 {f}")
    _ = (chart_mod, msg_mod)

    # 2) 归因不明必须不出图
    try:
        ChartSpec(decision="emit", need_type="no_attribution", chart_type="line",
                  caption="x")
        problems.append("ChartSpec 未拦截 no_attribution 出图")
    except Exception:
        pass

    # 3) skip 必须给 reason
    try:
        ChartSpec(decision="skip", need_type="risk")
        problems.append("ChartSpec 未拦截 skip 无 reason")
    except Exception:
        pass

    # 4) emit 必须给 caption
    try:
        ChartSpec(decision="emit", need_type="risk", data_ref="series.close.hfq")
        problems.append("ChartSpec 未拦截 emit 无 caption")
    except Exception:
        pass

    # 5) 未来证据必须被 ArgDoc 拦住
    try:
        ArgDoc(task="stock_outlook", as_of="2025-01-04",
               evidence=[Evidence(id="e1", source="2025年报", doc_type="announcement",
                                  publish_time="2025-03-20")])
        problems.append("ArgDoc 未拦截未来证据")
    except Exception:
        pass

    # 6) 同日证据也算泄漏（保守时间规则）
    try:
        ArgDoc(task="stock_outlook", as_of="2025-01-04",
               evidence=[Evidence(id="e2", source="公告", doc_type="announcement",
                                  publish_time="2025-01-04 20:00:00")])
        problems.append("ArgDoc 未拦截同日证据")
    except Exception:
        pass

    # 7) 正常样例可通过
    doc = ArgDoc(task="stock_outlook", as_of="2025-01-04",
                 evidence=[Evidence(id="e1", source="年报", doc_type="report",
                                    publish_time="2024-03-15")],
                 claims=[Claim(id="c1", type="fact", text="营收增长", evidence=["e1"])])
    if doc.dangling_evidence():
        problems.append("dangling_evidence 对合法引用误报")

    # 8) drop_hallucinated
    msg = AgentMessage(sender="a", role="analyst", task="stock_outlook", as_of="2025-01-04",
                       claims=[Claim(id="c1", type="fact", text="x", evidence=["nope"])],
                       evidence_used=["e1"])
    if msg.drop_hallucinated() != 1 or msg.claims:
        problems.append("drop_hallucinated 行为不正确")

    if problems:
        print(f"契约检查发现 {len(problems)} 个问题：")
        for p in problems:
            print("  -", p)
        return 1
    print("契约检查全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())