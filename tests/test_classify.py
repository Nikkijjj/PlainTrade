"""classify() 的回归测试：锁住"半年度/摘要/英文"的误判，防止再改回来。"""
from __future__ import annotations

import pytest

from data.sources.em_notice import classify


@pytest.mark.parametrize("title, expected", [
    # 核心 bug：半年度含"年度报告"子串，必须判半年报
    ("平安银行:2024年半年度报告", "半年报"),
    ("平安银行:半年报董事会决议公告", "半年报"),   # "半年报"含"年报"子串
    ("招商银行:2024年中期报告", "半年报"),
    # 摘要/英文不要全文，归"其他"
    ("海康威视:2024年年度报告摘要", "其他"),
    ("海康威视:2024年年度报告(英文版)", "其他"),
    ("美的集团:2023年第一季度报告全文(英文)", "其他"),
    # 正常情况
    ("贵州茅台:贵州茅台2024年年度报告", "年报"),
    ("贵州茅台:2024年第三季度报告", "季报"),
    ("平安银行:2024年年度权益分派实施公告", "分红"),
    ("平安银行:关于副行长任职资格核准的公告", "其他"),
])
def test_classify(title: str, expected: str) -> None:
    assert classify(title) == expected, f"{title} 应判为 {expected}，实际 {classify(title)}"


def test_quarter_report_not_annual() -> None:
    """一季度报告不含"年报"，不能落入年报分支。"""
    assert classify("海康威视:2025年第一季度报告") == "季报"
