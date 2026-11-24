"""编排图：node 列表 + 每个 node 的超时与降级行为。

降级约定：
  skip    跳过，写入 information_gaps
  default 用保守默认值（图表=不出图；越界拦截=拒答）
  abort   无法形成结论，整体失败
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    name: str
    timeout_s: int
    on_fail: str        # skip | default | abort


NODES = (
    Node("router", 5, "default"),
    Node("fetch", 30, "abort"),
    Node("analysts", 60, "skip"),
    Node("debate", 20, "skip"),
    Node("manager", 30, "abort"),
    Node("summarize", 20, "abort"),
    Node("termgate", 10, "skip"),
    Node("chart", 10, "default"),
    Node("guardrail", 5, "default"),
)