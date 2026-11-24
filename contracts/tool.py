"""工具层契约：agent 与外部世界的唯一边界。禁止在这里引用任何业务模块。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    params_schema: dict = Field(default_factory=dict)
    returns: str = "描述返回值结构"
    timeout_s: int = 20


class ToolCall(BaseModel):
    name: str
    args: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: str | None = None
    elapsed_ms: int = 0