"""结构自检：目录清单 / README 三行 / __init__ / 禁用文件名 / 反向 import / 文件行数 / prompts。

用法：python -m scripts.check_structure
返回码 0 = 全部通过。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "README.md", "pyproject.toml", ".env.example", ".gitignore", "Makefile", "conftest.py",
    "config/__init__.py", "config/settings.py", "config/chart_contracts.yaml", "config/jargon.json",
    "contracts/__init__.py", "contracts/argdoc.py", "contracts/chart.py",
    "contracts/brief.py", "contracts/message.py", "contracts/tool.py",
    "tools/__init__.py", "tools/registry.py", "tools/market.py", "tools/docs.py",
    "tools/finance.py", "tools/news.py",
    "llm/__init__.py", "llm/client.py", "llm/structured.py", "llm/cache.py", "llm/cost.py",
    "observability/__init__.py", "observability/trace.py", "observability/logger.py",
    "memory/__init__.py", "memory/chat_store.py",
    "data/__init__.py", "data/db.py", "data/schema.sql", "data/build_db.py",
    "data/sources/__init__.py", "data/sources/base.py", "data/sources/em_quote.py",
    "data/sources/em_notice.py", "data/sources/em_finance.py", "data/sources/em_board.py",
    "data/sources/em_news.py",
    "research/__init__.py", "research/index.py", "research/retrieve.py",
    "agents/__init__.py", "agents/base.py", "agents/router.py", "agents/debate.py",
    "agents/manager.py", "agents/analysts/__init__.py",
    "agents/analysts/disclosure.py", "agents/analysts/fundamental.py",
    "agents/analysts/technical.py",
    "adapt/__init__.py", "adapt/summarize.py", "adapt/termgate.py", "adapt/fidelity.py",
    "adapt/chart.py", "adapt/render.py", "adapt/attribution.py",
    "guardrails/__init__.py", "guardrails/escalation.py",
    "pipeline/__init__.py", "pipeline/tasks.py", "pipeline/graph.py", "pipeline/run.py",
    "ui/__init__.py", "ui/app.py", "ui/blocks.py", "ui/debug.py",
    "eval/__init__.py", "eval/metrics/__init__.py", "eval/runners/__init__.py",
    "scripts/__init__.py", "scripts/check_structure.py", "scripts/check_contracts.py",
    "tests/__init__.py", "tests/test_leakage.py", "tests/test_contracts.py",
    "tests/test_guardrails.py", "tests/test_adapt_golden.py",
]

FORBIDDEN_NAMES = {"utils.py", "helpers.py", "common.py", "misc.py", "temp.py"}

# 允许的依赖方向（只针对本项目内部包）
ALLOWED = {
    "config": {"config"},
    "contracts": {"contracts"},
    "observability": {"observability", "config"},
    "memory": {"memory", "contracts", "config"},
    "llm": {"llm", "contracts", "config", "observability"},
    "data": {"data", "config", "observability"},
    "research": {"research", "data", "config"},
    "tools": {"tools", "contracts", "data", "research", "config"},
    "agents": {"agents", "contracts", "tools", "llm", "memory", "observability", "config"},
    "adapt": {"adapt", "contracts", "config", "llm"},
    "guardrails": {"guardrails", "contracts", "llm", "config"},
    "pipeline": {"pipeline", "agents", "adapt", "guardrails", "tools", "research",
                 "data", "llm", "observability", "memory", "contracts", "config"},
    "ui": {"ui", "pipeline", "contracts", "config"},
    "eval": {"eval", "contracts", "data", "pipeline", "config"},
    "scripts": None,          # 一次性工具，允许任何
    "tests": None,
}
LOCAL = set(ALLOWED)

MAX_LINES = 200


def fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def check_required(problems: list[str]) -> None:
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            fail(problems, f"缺少文件：{rel}")


def packages() -> list[Path]:
    return sorted(p for p in ROOT.rglob("__init__.py")
                  if "__pycache__" not in str(p) and p.parent != ROOT)


def check_packages(problems: list[str]) -> None:
    for init in packages():
        d = init.parent
        readme = d / "README.md"
        rel = d.relative_to(ROOT).as_posix()
        if not readme.exists():
            fail(problems, f"包缺少 README.md：{rel}")
            continue
        text = readme.read_text(encoding="utf-8")
        for key in ("职责：", "禁止：", "接口："):
            if key not in text:
                fail(problems, f"README 缺少「{key}」：{rel}/README.md")


def check_names(problems: list[str]) -> None:
    for p in ROOT.rglob("*"):
        if p.is_file() and p.name in FORBIDDEN_NAMES:
            fail(problems, f"禁用文件名：{p.relative_to(ROOT).as_posix()}")


def check_imports(problems: list[str]) -> None:
    for py in ROOT.rglob("*.py"):
        s = str(py)
        if "__pycache__" in s or py.name == "conftest.py":
            continue
        rel = py.relative_to(ROOT)
        owner = rel.parts[0] if len(rel.parts) > 1 else None
        if owner not in ALLOWED:
            continue
        allowed = ALLOWED[owner]
        if allowed is None:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            fail(problems, f"语法错误：{rel.as_posix()} -> {e}")
            continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods = [node.module]
            for m in mods:
                top = m.split(".")[0]
                if top in LOCAL and top not in allowed:
                    fail(problems, f"反向依赖：{rel.as_posix()} 不允许 import {top}/")
                    break


def check_lines(problems: list[str]) -> None:
    for py in ROOT.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        n = len(py.read_text(encoding="utf-8").splitlines())
        if n > MAX_LINES:
            fail(problems, f"文件超 {MAX_LINES} 行（{n}）：{py.relative_to(ROOT).as_posix()}")


def check_prompts(problems: list[str]) -> None:
    pdir = ROOT / "config" / "prompts"
    files = sorted(pdir.glob("*.md"))
    if len(files) != 14:
        fail(problems, f"prompts 应为 14 个，实际 {len(files)}")
    for f in files:
        text = f.read_text(encoding="utf-8")
        if not text.lstrip().startswith("<!--"):
            fail(problems, f"prompt 缺少契约头：{f.name}")
            continue
        for key in ("输入：", "输出：", "约束："):
            if key not in text:
                fail(problems, f"prompt 缺少「{key}」：{f.name}")


def main() -> int:
    problems: list[str] = []
    check_required(problems)
    check_packages(problems)
    check_names(problems)
    check_imports(problems)
    check_lines(problems)
    check_prompts(problems)

    files = [p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in str(p)]
    print(f"检查目录：{ROOT}")
    print(f"文件总数：{len(files)}｜包数：{len(packages())}")
    if problems:
        print(f"\n发现 {len(problems)} 个问题：")
        for p in problems:
            print("  -", p)
        return 1
    print("\n结构检查全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())