"""短期对话状态。只存在内存里，进程结束即丢；如需持久化用 JSONL，不入库。

⚠️ 合规红线：绝不保存用户的资产、收入、持仓等真实财务信息。
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class Turn:
    role: str                  # user / assistant
    text: str
    meta: dict = field(default_factory=dict)


class ChatStore:
    def __init__(self, max_turns: int = 8) -> None:
        self._turns: deque[Turn] = deque(maxlen=max_turns)

    def push(self, turn: Turn) -> None:
        self._turns.append(turn)

    def recent(self, n: int = 4) -> list[Turn]:
        return list(self._turns)[-n:]

    def clear(self) -> None:
        self._turns.clear()


store = ChatStore()