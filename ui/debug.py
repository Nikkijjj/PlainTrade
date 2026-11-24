"""调试页：ArgDoc / ChartSpec / span。仅 ?debug=1 可见。"""
from __future__ import annotations

import json

import streamlit as st


def render(argdoc: dict, chartspec: dict, audit: dict) -> None:
    for title, payload in (("ArgDoc", argdoc), ("ChartSpec", chartspec), ("审计", audit)):
        st.subheader(title)
        st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")