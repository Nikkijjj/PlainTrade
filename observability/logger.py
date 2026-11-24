"""JSONL 追加写。审计日志不进数据库，便于 grep 与 diff。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from config.settings import settings


def append_jsonl(filename: str, record: dict) -> None:
    d = Path(settings.log_dir)
    d.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with (d / filename).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")