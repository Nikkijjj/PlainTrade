"""Streamlit 入口（薄）。只做：输入 -> pipeline.run -> 渲染。"""
from __future__ import annotations

import streamlit as st

from pipeline.run import run
from pipeline.tasks import TASKS

st.set_page_config(page_title="PlainTrade", page_icon="📈", layout="centered")
st.title("PlainTrade")
st.caption("帮你看懂市场，不替你决定")

with st.sidebar:
    as_of = st.text_input("决策日 as_of", "2025-03-14")
    for t in TASKS.values():
        st.code(t.example, language=None)

q = st.chat_input("问点什么…")
if q:
    st.chat_message("user").write(q)
    with st.chat_message("assistant"):
        try:
            from ui.blocks import render_brief
            render_brief(run(q, as_of=as_of))
        except NotImplementedError as e:
            st.warning(f"模块未实现：{e}")