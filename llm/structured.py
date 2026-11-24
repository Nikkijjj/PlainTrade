"""结构化输出：schema 校验 + 一次修复重试。禁止业务代码裸 json.loads。"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from llm.client import complete


class StructuredOutputError(RuntimeError):
    """模型两次都没给出合法 JSON —— 由调用方决定降级策略。"""


def extract_json(raw: str) -> dict:
    """从模型输出里抠出第一个 JSON 对象（容忍 ```json 包裹与前后废话）。"""
    s = raw.strip()
    if "```" in s:
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            s = re.sub(r"^\s*json\s*", "", s, flags=re.I)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("输出中没有 JSON 对象")
    return json.loads(s[i:j + 1])


def complete_json(prompt_name: str, schema: type[BaseModel], *,
                  repair_attempts: int = 1, **variables: object) -> BaseModel:
    """调用模型并校验成 schema；解析失败时把错误回喂一次。"""
    raw = complete(prompt_name, **variables)
    last_err = ""
    for attempt in range(repair_attempts + 1):
        try:
            return schema.model_validate(extract_json(raw))
        except (ValueError, ValidationError) as e:
            last_err = str(e)
            if attempt >= repair_attempts:
                break
            raw = complete(
                prompt_name,
                extra_instruction=(
                    f"你上次的输出无法通过校验：{last_err}\n"
                    "只输出合法 JSON，不要任何解释、不要 markdown 代码块。"
                ),
                **variables,
            )
    raise StructuredOutputError(f"{prompt_name} 结构化输出失败：{last_err}")