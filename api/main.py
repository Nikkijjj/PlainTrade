"""FastAPI 入口：托管单个 HTML + 提供 /api/ask。

设计要点
--------
* 前端只拿 PlainBrief JSON，不做任何业务判断。
* pipeline 还没实现时返回 mock（MOCK_FALLBACK），让前端能独立开发。
* 图表以 base64 内嵌进 JSON，避免静态路径与 CORS 问题。
"""
from __future__ import annotations

import base64
import json as _json
import queue as _queue
import threading as _threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI  # type: ignore[import-not-found]
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # type: ignore[import-not-found]
from fastapi.staticfiles import StaticFiles  # type: ignore[import-not-found]
from pydantic import BaseModel  # type: ignore[import-not-found]

from config.paths import frontend_dir
from config.settings import settings

CST = timezone(timedelta(hours=8))
FRONTEND = frontend_dir()
app = FastAPI(title="PlainTrade", version="0.1.0")


class AskRequest(BaseModel):
    query: str
    as_of: str | None = None


def _now_as_of() -> str:
    """live 模式用当前时刻；回放模式用「今天」（当天公告不可见）。"""
    now = datetime.now(CST)
    return now.strftime("%Y-%m-%d %H:%M:%S") if settings.mode == "live" else now.strftime("%Y-%m-%d")


def _mock_brief(query: str) -> dict:
    """pipeline 未实现时的兜底，字段与 contracts/brief.py 完全一致。"""
    return {
        "task": "stock_outlook",
        "one_liner": "（mock）生意还在增长，但速度慢下来了，估值已经把较好的预期算进去了。",
        "stance_plain": "谨慎偏乐观",
        "confidence_plain": {"value": "大概六成",
                             "anchor": "六成约等于抛硬币偏一点，不是「很确定」"},
        "why": [{"point": "最新一期营收比去年同期多 12%，增速回落 3 个百分点。",
                 "evidence": ["e1"], "glossary_id": "t1"}],
        "charts": [{"spec": {"decision": "skip", "need_type": "no_attribution",
                             "chart_type": None, "data_ref": "",
                             "annotations": [], "caption": "",
                             "reason": "pipeline 未实现，暂不渲染图表"},
                    "image_path": ""}],
        "what_would_change_our_mind": ["下季度增速掉到 5% 以下"],
        "what_you_should_not_do": ["这不是让你买或卖。"],
        "glossary": [{"id": "t1", "term": "估值", "plain": "简单说就是贵不贵",
                      "analogy": "同样的铺子，租金越高回本越慢"}],
        "citations": ["（mock 数据，非真实来源）"],
        "audit": {"mode": "mock", "query": query, "note": "pipeline.run 尚未实现"},
    }


def _png_data_url(path: str) -> str:
    """把渲染好的 PNG 塞成 data URL，前端 <img src> 直接用。"""
    p = Path(path)
    if not p.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def _inline_images(brief) -> None:
    """响应前把 image_path 换成 base64，前端无需再取静态文件。"""
    for block in getattr(brief, "charts", []) or []:
        ip = getattr(block, "image_path", "")
        if ip and not ip.startswith("data:"):
            block.image_path = _png_data_url(ip)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "mode": settings.mode, "as_of": _now_as_of(),
            "db": str(settings.db_path), "db_exists": Path(settings.db_path).exists()}


@app.post("/api/ask")
def ask(req: AskRequest):
    """跑一次完整请求。失败时返回 ok=false + error，前端显示降级提示。"""
    as_of = req.as_of or _now_as_of()
    try:
        from pipeline.run import run                       # 延迟导入：避免启动即失败
        brief = run(req.query, as_of=as_of)
        _inline_images(brief)
        return JSONResponse({"ok": True, "brief": brief.model_dump(mode="json"),
                             "as_of": as_of, "mode": settings.mode})
    except NotImplementedError as e:
        return JSONResponse({"ok": True, "brief": _mock_brief(req.query),
                             "as_of": as_of, "mode": "mock",
                             "warning": f"pipeline 未实现：{e}"})
    except Exception as e:                                  # noqa: BLE001
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"},
                            status_code=500)


@app.post("/api/ask/stream")
def ask_stream(req: AskRequest):
    """流式：NDJSON，每行一个事件。

    事件类型：
      {"type":"stage","stage":"router","label":"正在理解你的问题…"}  ← 进度
      {"type":"brief","ok":true,"brief":{...},"as_of":...}            ← 最终结果
      {"type":"error","error":"..."}
    """
    as_of = req.as_of or _now_as_of()
    q: "_queue.Queue" = _queue.Queue()

    def _worker() -> None:
        def on_event(evt: dict) -> None:
            q.put(evt)
        try:
            from pipeline.run import run                   # 延迟导入
            brief = run(req.query, as_of=as_of, on_event=on_event)
            _inline_images(brief)
            q.put({"type": "brief", "ok": True,
                   "brief": brief.model_dump(mode="json"),
                   "as_of": as_of, "mode": settings.mode})
        except Exception as e:                              # noqa: BLE001
            q.put({"type": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            q.put(None)                                     # 哨兵

    _threading.Thread(target=_worker, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is None:
                break
            yield _json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)