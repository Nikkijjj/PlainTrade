"""打包成 Windows 可运行产物（PyInstaller onedir）。

为什么用 onedir 而不是 onefile：
  * onefile 每次启动都要解压到临时目录（冷启动 5-10 秒），且杀毒误报率高
  * onedir 启动快、报错可排查、误报少；分发时打成一个 zip 即可

用法（在项目根目录）：
    pip install -e ".[web]" pyinstaller
    python -m scripts.build_exe            # 产出 dist/PlainTrade/PlainTrade.exe
    python -m scripts.build_exe --onefile  # 谨慎：体积更大、更慢

产物结构（dist/PlainTrade/）：
    PlainTrade.exe
    _internal/            PyInstaller 依赖
    frontend/             界面资源（--add-data）
    data_files/           数据快照（若存在）
    cases/                预生成演示案例
    config.env.example
    使用说明.txt
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # scripts/ 的上一级 = 项目根
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "PlainTrade"

# uvicorn / pydantic 有大量动态导入，PyInstaller 静态分析抓不到 → 必须显式声明
HIDDEN_IMPORTS = [
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    "api.main", "pipeline.run", "pipeline.tasks", "pipeline.graph",
    "agents.router", "agents.manager", "agents.base",
    "adapt.summarize", "adapt.chart", "adapt.termgate",
    "guardrails.escalation", "tools.registry", "data.db", "data.sources.em_quote",
    "pydantic", "pydantic_core", "pydantic_settings",
]

# 需要一起打进包里的目录
ADD_DATA = [("frontend", "frontend")]

# 排除掉的大件（能显著减小体积）
EXCLUDES = ["tkinter", "test", "unittest", "pydoc_data", "IPython", "jupyter"]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def build(onefile: bool = False) -> Path:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--onedir" if not onefile else "--onefile",
        "--console",                       # 保留控制台：老师能看到地址与报错
        str(ROOT / "scripts" / "launcher.py"),
    ]
    for mod in HIDDEN_IMPORTS:
        args += ["--hidden-import", mod]
    for src, dst in ADD_DATA:
        if (ROOT / src).exists():
            sep = ";" if sys.platform == "win32" else ":"
            args += ["--add-data", f"{ROOT / src}{sep}{dst}"]
    for mod in EXCLUDES:
        args += ["--exclude-module", mod]

    run(args)
    out = DIST / (f"{APP_NAME}.exe" if onefile else APP_NAME)
    return out


def assemble(out: Path) -> None:
    """把 exe 与「必须外置」的资源放到一起（data/、cases/、env 模板、说明）。"""
    target = out if out.is_dir() else DIST
    for name in ("cases",):
        src = ROOT / name
        if src.exists():
            shutil.copytree(src, target / name, dirs_exist_ok=True)
    df = ROOT / "data_files"
    if df.exists():
        (target / "data_files").mkdir(exist_ok=True)
        for f in df.glob("*.db"):
            shutil.copy2(f, target / "data_files" / f.name)
    env = ROOT / ".env.example"
    if env.exists():
        shutil.copy2(env, target / "config.env.example")
    (target / "使用说明.txt").write_text(
        "PlainTrade 使用说明\n"
        "==================\n\n"
        "1. 双击 PlainTrade.exe\n"
        "2. 稍等 2-5 秒，浏览器会自动打开界面\n"
        "3. 注册/登录页不用管：直接点示例问题即可（内置演示数据，无需联网）\n"
        "4. 想用实时模式：把 config.env.example 改名为 config.env，填 DEEPSEEK_API_KEY\n"
        "5. 用完关闭那个黑色命令窗口即可退出\n\n"
        "如果双击没反应或被杀毒软件拦截：\n"
        "  · 右键 exe → 属性 → 解除锁定 → 再试\n"
        "  · 或加入杀毒软件白名单\n"
        "  · 或改用同目录的 start.bat（需要机器已装 Python 3.11+）\n",
        encoding="utf-8")
    print(f"\n产物目录：{target}")
    print("打 zip 发给老师：把整个目录压缩即可（不要只发 exe）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--onefile", action="store_true", help="打成单个 exe（更慢更容易误报）")
    ap.add_argument("--no-assemble", action="store_true", help="只打包，不拷贝资源")
    args = ap.parse_args()

    if not (ROOT / "scripts" / "launcher.py").exists():
        print("请在项目根目录运行本脚本")
        return 1
    for p in (BUILD, DIST):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    out = build(args.onefile)
    if not args.no_assemble:
        assemble(out)
    print("\n完成。双击验证：", out / (APP_NAME + ".exe") if out.is_dir() else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())