"""统一模型调用：超时、重试、日志。所有 agent 只走这里。

D-01 实现要点（见 Agent开发需求 R-01）：
  * requests 直连 DeepSeek（OpenAI 兼容协议），不引入 openai 包
  * temperature 默认 0（可复现是评估的前提）
  * 超时 60s，失败重试 2 次（0.8s / 1.6s 退避）
  * 每次调用写一行 span JSONL（prompt 名/hash、token、usd、耗时、run_id）
  * key 为空时报清晰中文错误，不吐 401 traceback
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from string import Template

import requests

from config.paths import resource_dir
from config.settings import settings
from llm.cost import usd
from observability.logger import append_jsonl
from observability.trace import current_run_id

# 用 resource_dir() 而非相对路径：打包成 exe 后 cwd 不是项目根，相对路径会找不到提示词
PROMPT_DIR = resource_dir() / "config" / "prompts"
BASE_URL = "https://api.deepseek.com/chat/completions"
RETRIES = 3                      # 首次 + 重试 2 次
TIMEOUT_S = 60


def load_prompt(name: str) -> str:
    p = PROMPT_DIR / f"{name}.md"
    if not p.exists():
        raise FileNotFoundError(f"找不到提示词：{p}")
    return p.read_text(encoding="utf-8")


def prompt_hash(name: str) -> str:
    return hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest()[:16]


def render(name: str, **variables: object) -> str:
    """用 string.Template 渲染（$var 语法），避免和 JSON 花括号打架。

    非字符串变量（dict/list）先 json.dumps，否则会插成 Python repr。
    """
    clean = {k: (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str))
             for k, v in variables.items()}
    return Template(load_prompt(name)).safe_substitute(**clean)


def _log_span(prompt_name: str, usage: dict, elapsed_ms: int) -> None:
    """每次调用记一行，供成本与延迟审计（失败也会由调用方 span 记录）。"""
    pt = usage.get("prompt_tokens") or 0
    ct = usage.get("completion_tokens") or 0
    append_jsonl("spans.jsonl", {
        "node": "llm.complete",
        "run_id": current_run_id(),
        "prompt_name": prompt_name,
        "prompt_hash": prompt_hash(prompt_name),
        "model": settings.llm_model,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "usd": usd(settings.llm_model, pt, ct),
        "elapsed_ms": elapsed_ms,
        "status": "ok",
    })


def complete(prompt_name: str, *, temperature: float | None = None,
             max_tokens: int | None = None, **variables: object) -> str:
    """渲染提示词 → 调 DeepSeek → 返回纯文本。"""
    # structured.complete_json 的修复回喂会传 extra_instruction（追加到正文，不在提示词里占位）
    extra = variables.pop("extra_instruction", None)
    text = render(prompt_name, **variables)
    if extra:
        text = f"{text}\n\n{extra}"

    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY：请在 .env 里填 key（见 .env.example）")

    temp = temperature if temperature is not None else settings.llm_temperature
    max_tok = max_tokens if max_tokens is not None else settings.llm_max_tokens
    payload = {"model": settings.llm_model,
               "messages": [{"role": "user", "content": text}],
               "temperature": temp, "max_tokens": max_tok}
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}",
               "Content-Type": "application/json"}

    t0 = time.perf_counter()
    last_err: Exception | None = None
    for attempt in range(RETRIES):
        try:
            r = requests.post(BASE_URL, json=payload, headers=headers, timeout=TIMEOUT_S)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            _log_span(prompt_name, data.get("usage") or {},
                      int((time.perf_counter() - t0) * 1000))
            return content
        except Exception as e:                       # noqa: BLE001
            last_err = e
            time.sleep(0.8 * (2 ** attempt))
    raise RuntimeError(f"模型调用失败（{prompt_name}，重试 {RETRIES} 次）：{last_err}")
