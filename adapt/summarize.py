"""结论压缩：stance + confidence -> 一句话 + 人话置信度。

映射固定（不许自由发挥）：
  >=0.70 比较有把握 / 0.55-0.70 大概六成 / 0.45-0.55 说不出高下 / <0.45 弃权
"""
from __future__ import annotations

from contracts.brief import ConfidencePlain

BANDS = (
    (0.70, "比较有把握", "大约十次里对七次以上"),
    (0.55, "大概六成", "六成约等于抛硬币偏一点，不是「很确定」"),
    (0.45, "说不出高下", "我们的证据互相打平，等于没结论"),
)
NO_VIEW = ConfidencePlain(value="没有明确看法", anchor="证据不够，我们就不给方向")


def plain_confidence(confidence: float) -> ConfidencePlain:
    for threshold, value, anchor in BANDS:
        if confidence >= threshold:
            return ConfidencePlain(value=value, anchor=anchor)
    return NO_VIEW


def summarize(argdoc) -> tuple[str, str, ConfidencePlain]:
    """返回 (one_liner, stance_plain, confidence_plain)。"""
    raise NotImplementedError("TODO(C)")