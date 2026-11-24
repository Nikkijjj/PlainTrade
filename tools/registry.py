"""工具注册表。agent 只通过这里调工具，不许直接 import data/。"""
from __future__ import annotations

import time
from typing import Callable

from contracts.tool import ToolCall, ToolResult, ToolSpec

_REGISTRY = {}


def register(spec: ToolSpec, fn: Callable) -> None:
    if spec.name in _REGISTRY:
        raise ValueError(f"工具重复注册：{spec.name}")
    _REGISTRY[spec.name] = (spec, fn)


def get(name: str):
    return _REGISTRY.get(name)


def describe_all() -> list[dict]:
    return [spec.model_dump() for spec, _ in _REGISTRY.values()]


def call(req: ToolCall) -> ToolResult:
    """统一入口：未知工具/异常/未实现都转成 ok=False，让 agent 能自我修正。"""
    item = _REGISTRY.get(req.name)
    if item is None:
        return ToolResult(ok=False, error=f"未知工具：{req.name}")
    spec, fn = item
    t0 = time.perf_counter()
    elapsed = lambda: int((time.perf_counter() - t0) * 1000)   # noqa: E731
    try:
        return ToolResult(ok=True, data=fn(**req.args), elapsed_ms=elapsed())
    except NotImplementedError as e:
        return ToolResult(ok=False, error=f"工具未实现：{e}", elapsed_ms=elapsed())
    except Exception as e:                                       # noqa: BLE001
        return ToolResult(ok=False, error=f"{type(e).__name__}: {e}", elapsed_ms=elapsed())