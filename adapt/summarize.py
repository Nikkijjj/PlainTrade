"""结论压缩：stance + confidence -> 一句话 + 人话置信度。

映射固定（不许自由发挥）：
  >=0.70 比较有把握 / 0.55-0.70 大概六成 / 0.45-0.55 说不出高下 / <0.45 弃权
"""
from __future__ import annotations

from contracts.argdoc import Stance
from contracts.brief import ConfidencePlain

BANDS = (
    (0.70, "比较有把握", "大约十次里对七次以上"),
    (0.55, "大概六成", "六成约等于抛硬币偏一点，不是「很确定」"),
    (0.45, "说不出高下", "我们的证据互相打平，等于没结论"),
)
NO_VIEW = ConfidencePlain(value="没有明确看法", anchor="证据不够，我们就不给方向")

STANCE_PLAIN = {
    Stance.POSITIVE: "比较乐观",
    Stance.MILDLY_POSITIVE: "谨慎偏乐观",
    Stance.NEUTRAL: "中性",
    Stance.MILDLY_NEGATIVE: "谨慎偏谨慎",
    Stance.NEGATIVE: "比较悲观",
    Stance.NO_VIEW: "没有明确看法",
}


def plain_confidence(confidence: float) -> ConfidencePlain:
    for threshold, value, anchor in BANDS:
        if confidence >= threshold:
            return ConfidencePlain(value=value, anchor=anchor)
    return NO_VIEW


def summarize(argdoc) -> tuple[str, str, ConfidencePlain]:
    """返回 (one_liner, stance_plain, confidence_plain)。D-03 用确定性实现，
    D-04（C）再换成 LLM 压缩 + 第二人称短句。"""
    stance_plain = STANCE_PLAIN.get(argdoc.stance, "没有明确看法")
    conf = plain_confidence(argdoc.confidence)

    if argdoc.stance is Stance.NO_VIEW or not argdoc.claims:
        one_liner = "证据不够，我们先不下结论"
    else:
        first = argdoc.claims[0].text.strip()
        one_liner = first if len(first) <= 30 else first[:29] + "…"
    return one_liner, stance_plain, conf
