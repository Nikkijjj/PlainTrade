"""统一模型调用：超时、重试、日志。所有 agent 只走这里。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from string import Template

from config.settings import settings

PROMPT_DIR = Path("config/prompts")


def load_prompt(name: str) -> str:
    p = PROMPT_DIR / f"{name}.md"
    if not p.exists():
        raise FileNotFoundError(f"找不到提示词：{p}")
    return p.read_text(encoding="utf-8")


def prompt_hash(name: str) -> str:
    return hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest()[:16]


def render(name: str, **variables: object) -> str:
    """用 string.Template 渲染（$var 语法），避免和 JSON 花括号打架。"""
    return Template(load_prompt(name)).safe_substitute(**variables)


def complete(prompt_name: str, *, temperature: float | None = None,
             max_tokens: int | None = None, **variables: object) -> str:
    """渲染 → 调模型 → 返回文本。

    TODO(B): 接 DeepSeek / Qwen。temperature 默认取 settings（0）。
    每次调用必须写一行 JSONL（observability/logger）。
    """
    _ = render(prompt_name, **variables)
    _ = temperature if temperature is not None else settings.llm_temperature
    _ = max_tokens if max_tokens is not None else settings.llm_max_tokens
    raise NotImplementedError("TODO(B): 实现模型调用")