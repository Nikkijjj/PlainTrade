"""统一路径解析（config 层：任何包都可以 import）。

源码运行 vs PyInstaller 打包后（sys.frozen）必须都能找到文件。
这是 PyInstaller 项目最高频的崩溃原因：打包后 __file__ 指向临时解压目录，
用相对路径找 frontend/ 或 data/ 就会报"文件不存在"。

注意：本文件在 config/ 下，源码模式的"项目根"是它的**上两级**。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 源码运行时的项目根（config/paths.py -> config/ -> 根）
_SOURCE_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """只读资源（frontend/ 等）所在目录。

    打包后是 sys._MEIPASS（临时解压目录），源码运行时是项目根。
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _SOURCE_ROOT


def app_dir() -> Path:
    """可写目录：exe 所在目录（源码运行时是项目根）。

    data_files/、config.env、logs/ 都放这里 —— 绝不能放进 _MEIPASS（只读且每次解压）。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _SOURCE_ROOT


def frontend_dir() -> Path:
    for base in (resource_dir(), app_dir()):
        p = base / "frontend"
        if (p / "index.html").exists():
            return p
    return resource_dir() / "frontend"


def data_dir() -> Path:
    return app_dir() / "data_files"


def ensure_dirs() -> None:
    for p in (data_dir(), app_dir() / "logs", app_dir() / "cases"):
        p.mkdir(parents=True, exist_ok=True)
