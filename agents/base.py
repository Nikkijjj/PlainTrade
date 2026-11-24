"""Agent 基类：load prompt -> structured call -> validate -> AgentMessage。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from contracts.argdoc import Claim
from contracts.message import AgentMessage
from llm.client import prompt_hash
from llm.structured import complete_json


class BaseAgent(ABC):
    name: str = "base"
    prompt_name: str = "base"
    schema: type[BaseModel] = BaseModel       # 子类必须覆盖

    @abstractmethod
    def build_vars(self, ctx: dict) -> dict:
        """把上下文变成 prompt 变量。"""

    @abstractmethod
    def parse(self, payload: BaseModel, ctx: dict) -> list[Claim]:
        """把结构化输出变成 claim 列表。"""

    def run(self, ctx: dict) -> AgentMessage:
        payload = complete_json(self.prompt_name, self.schema, **self.build_vars(ctx))
        msg = AgentMessage(
            sender=self.name, role="analyst",
            task=ctx.get("task", "stock_outlook"),
            code=ctx.get("code"), as_of=ctx["as_of"],
            claims=self.parse(payload, ctx),
            evidence_used=ctx.get("evidence_ids", []),
            meta={"prompt_hash": prompt_hash(self.prompt_name)},
        )
        msg.drop_hallucinated()
        return msg