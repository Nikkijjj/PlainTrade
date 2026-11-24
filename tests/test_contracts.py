"""契约回归：字段不许悄悄改名（三人并行开发的安全网）。"""
from __future__ import annotations

import pytest

from contracts.argdoc import ArgDoc
from contracts.brief import PlainBrief
from contracts.chart import ChartSpec


def test_argdoc_fields() -> None:
    for f in ("task", "as_of", "stance", "confidence", "claims", "evidence",
              "explanation_status", "invalidation_conditions"):
        assert f in ArgDoc.model_fields


def test_plainbrief_fields() -> None:
    for f in ("one_liner", "stance_plain", "confidence_plain", "why", "charts"):
        assert f in PlainBrief.model_fields


def test_chart_forbids_chart_when_unknown() -> None:
    with pytest.raises(Exception):
        ChartSpec(decision="emit", need_type="no_attribution", chart_type="line",
                  caption="x")


def test_chart_skip_requires_reason() -> None:
    with pytest.raises(Exception):
        ChartSpec(decision="skip", need_type="risk")