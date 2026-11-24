"""启动器冒烟测试：不需要 fastapi/uvicorn，用 stdlib 起假服务验证关键逻辑。

验证四件事（这四件事出错就是"老师双击打不开"）：
1. 端口探测：占用时能自动换端口
2. 就绪轮询：服务没起来时返回 False，起来后返回 True
3. 单实例锁：第二次获取应失败
4. 路径解析：模拟 sys.frozen，确认数据/资源目录指向正确位置

用法：python -m scripts.check_launcher
"""
from __future__ import annotations

import http.server
import os
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.launcher import free_port, health_ok, wait_ready   # noqa: E402
from config import paths as paths_mod                        # noqa: E402

OK, FAIL = "✓", "✗"
problems: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {OK if cond else FAIL} {msg}")
    if not cond:
        problems.append(msg)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):                                        # noqa: N802
        if self.path == "/api/health":
            body = b'{"ok":true,"mode":"replay"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, *a):                               # 关掉噪音
        pass


def serve(port: int) -> http.server.HTTPServer:
    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> int:
    print("[1] 端口探测")
    port = free_port(8765)
    check(port >= 8765, f"拿到空闲端口 {port}")
    # 占用该端口后再探测，应该自动换一个
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    port2 = free_port(port)
    check(port2 != port, f"端口 {port} 被占用时会换到 {port2}")
    blocker.close()

    print("\n[2] 就绪轮询")
    check(health_ok(port2, timeout=0.3) is False, "服务未起时 health 返回 False")
    srv = serve(port2)
    check(wait_ready(port2, timeout=5.0) is True, "服务起来后 wait_ready 返回 True")
    srv.shutdown()
    check(wait_ready(port2, timeout=0.6) is False, "服务关掉后 wait_ready 返回 False")

    print("\n[3] 单实例锁（跨进程语义）")
    from scripts.launcher import acquire_lock, pid_alive
    lockdir = Path("data_files/_lock")
    lockdir.mkdir(parents=True, exist_ok=True)
    lock = lockdir / "instance.lock"
    if lock.exists():
        lock.unlink()
    fh1, first1 = acquire_lock(lock)
    check(first1 is True, "空锁文件：拿到锁")
    # 模拟"活进程持锁"：写入本进程 PID（保证 alive，且语义等价于另一个在跑的实例）
    lock.write_text(str(os.getpid()), encoding="utf-8")
    fh2, first2 = acquire_lock(lock)
    check(first2 is False, "锁被活进程持有时：拒绝成为首实例（重复双击不会起两个服务）")
    # 模拟"残留锁"：写一个不可能存在的 PID
    lock.write_text("999999", encoding="utf-8")
    fh3, first3 = acquire_lock(lock)
    check(first3 is True, "残留锁（进程已死）：接管并成为首实例")
    check(pid_alive(999999) is False, "pid_alive 对已退出进程返回 False")
    check(pid_alive(os.getpid()) is True, "pid_alive 对自身返回 True")

    print("\n[4] 路径解析（模拟 PyInstaller 打包后）")
    root = Path(__file__).resolve().parent.parent
    check(paths_mod.resource_dir() == root, "源码模式：resource_dir 指向项目根")
    check(paths_mod.data_dir() == root / "data_files", "源码模式：data_dir 指向 data_files")
    sys.frozen = True                                       # type: ignore[attr-defined]
    fake = Path("data_files/_meipass"); fake.mkdir(parents=True, exist_ok=True)
    sys._MEIPASS = str(fake)                                # type: ignore[attr-defined]
    try:
        check(paths_mod.resource_dir() == fake, "打包模式：resource_dir 走 _MEIPASS")
        check("_meipass" not in str(paths_mod.data_dir()).lower(),
              f"打包模式：data_dir 不落在 _MEIPASS（实际 {paths_mod.data_dir()}）")
    finally:
        del sys.frozen                                      # type: ignore[attr-defined]
        del sys._MEIPASS                                    # type: ignore[attr-defined]

    print()
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for p in problems:
            print("  -", p)
        return 1
    print("启动器逻辑全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())