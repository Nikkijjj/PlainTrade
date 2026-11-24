"""exe 启动器：起 FastAPI 服务 → 等就绪 → 自动打开浏览器。

只用标准库（fastapi/uvicorn 在 run_server 内部才导入），好处是：
* 起服务失败的报错不会被 import 阶段的异常掩盖
* 这段逻辑可以脱离 fastapi 单独测试

用法（源码运行）：python -m scripts.launcher
"""
from __future__ import annotations

import http.client
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_PORT_TRIES = 20


def port_in_use(port: int, timeout: float = 0.2) -> bool:
    """能否连上代表已有人在监听。比 bind 探测可靠（见 free_port 注释）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((HOST, port)) == 0


def free_port(start: int = DEFAULT_PORT, tries: int = MAX_PORT_TRIES) -> int:
    """从 start 往上找一个可用端口。

    坑：Windows 上给探测 socket 设 SO_REUSEADDR 之后，bind 一个已被占用的端口
    也会"成功"（允许抢占），于是 get 到一个根本用不了的端口。所以这里两步走：
    ① 先 connect 探测是否有人在听；② 再裸 bind（Windows 默认独占）确认可用。
    """
    for offset in range(tries):
        port = start + offset
        if port_in_use(port):
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"{start}-{start + tries} 端口都被占用，请关掉其他程序再试")


def health_ok(port: int, timeout: float = 1.0) -> bool:
    """探测 /api/health 是否已就绪。"""
    try:
        conn = http.client.HTTPConnection(HOST, port, timeout=timeout)
        conn.request("GET", "/api/health")
        resp = conn.getresponse()
        ok = resp.status == 200
        resp.read()
        conn.close()
        return ok
    except OSError:
        return False


def wait_ready(port: int, timeout: float = 20.0, interval: float = 0.2) -> bool:
    """轮询直到服务就绪 —— 不能用固定 sleep，机器快慢差异很大。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_ok(port):
            return True
        time.sleep(interval)
    return False


def pid_alive(pid: int) -> bool:
    """进程是否还活着（跨平台，不依赖 psutil）。"""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if h:
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock(lock_path: Path):
    """单实例：重复双击时不再起第二个服务，直接开浏览器。

    用 PID 文件而不是文件字节锁 —— Windows 的字节锁是**进程级**的，
    同一个进程用另一个句柄还能再锁一次，起不到单实例效果。
    返回 (lock_path 或 None, 是否首个实例)。
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            old = int(lock_path.read_text(encoding="utf-8").strip() or 0)
        except (ValueError, OSError):
            old = 0
        if old and pid_alive(old):
            return None, False
        # 残留锁（上次崩溃没清）→ 直接接管
    try:
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
        return lock_path, True
    except OSError:
        return None, True                     # 拿不到锁就当首个实例，别阻塞用户


def run_server(port: int) -> None:
    """真正起服务（此处才导入 fastapi/uvicorn）。"""
    import uvicorn

    from api.main import app
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


def main() -> int:
    import argparse

    from config.paths import app_dir, ensure_dirs

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    ensure_dirs()
    lock_file, first = acquire_lock(app_dir() / "logs" / "instance.lock")

    if not first:
        # 已有实例：等它就绪后直接开浏览器
        for port in range(args.port, args.port + MAX_PORT_TRIES):
            if wait_ready(port, timeout=1.0):
                if not args.no_browser:
                    webbrowser.open(f"http://{HOST}:{port}")
                print(f"PlainTrade 已在运行：http://{HOST}:{port}")
                return 0
        print("检测到另一个实例的锁，但服务没响应。请关掉残留进程后重试。")
        return 1

    port = free_port(args.port)
    threading.Thread(target=run_server, args=(port,), daemon=True).start()

    if not wait_ready(port, timeout=25.0):
        print("服务启动超时。日志见 logs/ 目录。")
        return 2

    url = f"http://{HOST}:{port}"
    print("=" * 52)
    print(" PlainTrade 已启动")
    print(f" 界面地址：{url}")
    print(" 关闭本窗口即退出")
    print("=" * 52)
    if not args.no_browser:
        webbrowser.open(url)

    try:
        while True:                        # 保持进程存活
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        if fh:
            Path(fh).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())