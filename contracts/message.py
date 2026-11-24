"""agent 间通信。硬约束：claim 只能引用 evidence_used 里存在的证据。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .argdoc import Claim


class AgentMessage(BaseModel):
    sender: str
    role: str
    task: str
    code: str | None = None
    as_of: str
    claims: list[Claim] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    notes: str = ""
    meta: dict = Field(default_factory=dict)

    def drop_hallucinated(self) -> int:
        """丢掉引用了不存在证据的 claim，返回丢弃条数。"""
        known = set(self.evidence_used)
        before = len(self.claims)
        self.claims = [c for c in self.claims if all(e in known for e in c.evidence)]
        return before - len(self.claims)