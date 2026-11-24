"""追踪：run_id + 每 node 一条 span。失败也要落一条，否则最长的那条会消失。"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from observability.logger import append_jsonl, now_iso

_run_id: ContextVar[str] = ContextVar("run_id", default="-")
_span_file = "spans.jsonl"


def new_run_id() -> str:
    rid = f"r-{uuid.uuid4().hex[:12]}"
    _run_id.set(rid)
    return rid


def current_run_id() -> str:
    return _run_id.get()


@contextmanager
def span(node: str) -> Iterator[dict]:
    """用法：with span('manager') as s: s['stance'] = 'no_view'"""
    rec: dict = {"run_id": current_run_id(), "node": node, "status": "ok",
                 "started_at": now_iso(), "meta": {}}
    t0 = time.perf_counter()
    try:
        yield rec
    except Exception as e:                      # noqa: BLE001
        rec["status"] = "error"
        rec["meta"]["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        rec["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        append_jsonl(_span_file, rec)