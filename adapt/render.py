"""确定性渲染：ChartSpec + 数据 -> PNG。LLM 不接触任何数值。

D-03 实现 drawdown_curve / bar / line 三种最小版；D-12（C）再补齐相对线、堆叠柱等。
"""
from __future__ import annotations

import uuid
from pathlib import Path


def render(spec, data: dict, out_dir: Path) -> Path:
    """按 chart_type 画图，强制加 caption 与免责标注。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # 中文字体：不设会整图中文变方框（DejaVu Sans 无 CJK 字形）
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei",
                                       "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec.chart_type or 'chart'}_{uuid.uuid4().hex[:8]}.png"

    fig, ax = plt.subplots(figsize=(8, 4))

    if spec.chart_type == "drawdown_curve":
        close = data.get("close", [])
        dates = data.get("dates", [])
        if not close:
            raise ValueError("drawdown 需要 close 序列")
        peak, dd = -float("inf"), []
        for c in close:
            peak = max(peak, c)
            dd.append((c - peak) / peak * 100 if peak else 0.0)
        x = list(range(len(dd)))
        ax.plot(x, dd, color="#c0392b")
        ax.fill_between(x, dd, 0, color="#c0392b", alpha=0.15)
        ax.set_title("回撤曲线（%）")
        if dates:
            step = max(1, len(dates) // 6)
            ax.set_xticks(x[::step])
            ax.set_xticklabels(dates[::step], rotation=45, fontsize=8)
    elif spec.chart_type == "bar":
        names = data.get("names", [])
        values = data.get("values", [])
        colors = ["#c0392b" if v < 0 else "#27ae60" for v in values]
        ax.barh(names, values, color=colors)
        ax.set_title("板块涨跌幅（%）")
        ax.axvline(0, color="gray", lw=0.8)
    else:                                          # line
        close = data.get("close", [])
        dates = data.get("dates", [])
        x = list(range(len(close)))
        ax.plot(x, close, color="#2c3e50")
        ax.set_title("价格")
        if dates:
            step = max(1, len(dates) // 6)
            ax.set_xticks(x[::step])
            ax.set_xticklabels(dates[::step], rotation=45, fontsize=8)

    if spec.caption:
        fig.text(0.01, 0.01, spec.caption + "｜仅供理解，非投资建议",
                 fontsize=8, color="gray")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
