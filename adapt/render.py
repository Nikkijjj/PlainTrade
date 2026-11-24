"""确定性渲染：ChartSpec + 数据 -> PNG。LLM 不接触任何数值。

注意：matplotlib 与 numpy 2.x 可能冲突，venv 里建议 pin numpy<2 或装 matplotlib>=3.9。
"""
from __future__ import annotations

from pathlib import Path


def render(spec, data: dict, out_dir: Path) -> Path:
    """按 chart_contracts.yaml 取数画图，强制加 caption 与免责标注。"""
    raise NotImplementedError("TODO(C)")