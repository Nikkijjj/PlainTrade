"""渲染块：段落 / 图表 / 术语 / 依据折叠。纯展示。"""
from __future__ import annotations

import streamlit as st


def render_brief(b) -> None:
    st.markdown(f"**{b.one_liner}**")
    st.caption(f"{b.stance_plain}｜把握程度：{b.confidence_plain.value}"
               f"（{b.confidence_plain.anchor}）")
    for blk in b.charts:
        if blk.spec.decision.value == "emit" and blk.image_path:
            st.image(blk.image_path)
            st.caption(blk.spec.caption)
    for w in b.what_would_change_our_mind:
        st.markdown(f"- 会错在哪：{w}")
    if b.citations:
        with st.expander(f"{len(b.citations)} 条依据"):
            for c in b.citations:
                st.markdown(f"- {c}")