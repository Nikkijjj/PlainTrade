"""专业 K 线图预览：用真实 OHLCV 画「K线 + 均线 + 成交量」双面板。

这个脚本同时是 `adapt/render.py` 的原型 —— 说明"专业"是怎么做到的：
高 DPI、克制配色、去掉图表垃圾、不用双 y 轴（改双面板）、标注最大回撤。

产出：frontend/shots/kline_preview.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates                     # noqa: E402
import matplotlib.pyplot as plt                        # noqa: E402
import numpy as np                                     # noqa: E402
import pandas as pd                                    # noqa: E402
from matplotlib.gridspec import GridSpec               # noqa: E402
from matplotlib.patches import Rectangle               # noqa: E402

from data import db                                    # noqa: E402

# A 股习惯：涨红跌绿
UP, DOWN = "#c0392b", "#0f7b3f"
INK, MUTED, GRID = "#1f2937", "#9aa4b2", "#e8ebef"
OUT = Path("frontend/shots/kline_preview.png")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DengXian"],
    "axes.unicode_minus": False,
    "figure.dpi": 200,
    "savefig.dpi": 200,
})


def load(code: str, start: str, end: str) -> pd.DataFrame:
    df = db.series(code, start, end, adj="qfq")
    df["date"] = pd.to_datetime(df["date"])
    return df.reset_index(drop=True)


def draw(code: str, name: str, df: pd.DataFrame, out: Path) -> None:
    n = len(df)
    x = np.arange(n)
    o, h, l, c, v = (df[k].to_numpy() for k in ("open", "high", "low", "close", "volume"))
    up = c >= o
    w = 0.62

    fig = plt.figure(figsize=(8.6, 4.6))
    gs = GridSpec(2, 1, height_ratios=[3.4, 1], hspace=0.08)
    ax = fig.add_subplot(gs[0])
    axv = fig.add_subplot(gs[1], sharex=ax)

    # ── 价格面板：影线 + 实体 ──────────────────────
    ax.vlines(x[up], l[up], h[up], color=UP, lw=0.8, zorder=3)
    ax.vlines(x[~up], l[~up], h[~up], color=DOWN, lw=0.8, zorder=3)
    body = np.maximum(np.abs(c - o), (h - l) * 0.012)      # 十字星也给一点高度
    ax.bar(x[up], body[up], w, bottom=np.minimum(o, c)[up], color=UP, zorder=4)
    ax.bar(x[~up], body[~up], w, bottom=np.minimum(o, c)[~up], color=DOWN, zorder=4)

    # ── 均线 ─────────────────────────────────────
    close_s = pd.Series(c)
    for win, color, label in ((5, "#2f6fb5", "5 日均线"), (20, "#b07a2a", "20 日均线")):
        ma = close_s.rolling(win).mean()
        ax.plot(x, ma, color=color, lw=1.1, label=label, zorder=5)

    # ── 最大回撤标注（区间高亮 + 读数，不用任何坐标外元素）──
    peak = np.maximum.accumulate(c)
    dd = c / peak - 1
    j = int(np.argmin(dd))
    i = int(np.argmax(c[: j + 1]))
    if j > i:
        ax.axvspan(i, j, color="#c0392b", alpha=0.06, zorder=1)
        # 最低点用一个小三角标出来（放在坐标区内，避免出界）
        ax.plot([j], [l[j]], marker="v", ms=5, color=UP, zorder=6)
        # 读数用 axhes 坐标系放在右上角，绝不出界
        ax.text(0.985, 0.06,
                f"阴影区间最大回撤 −{abs(dd[j]) * 100:.0f}%\n"
                f"（{df['date'].iloc[i]:%Y-%m-%d} → {df['date'].iloc[j]:%Y-%m-%d}）",
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=8.2, color=UP, linespacing=1.5,
                bbox={"boxstyle": "round,pad=0.32", "fc": "#fff5f4",
                      "ec": "#f0cfcb", "lw": 0.7})

    # ── 决策日竖线 ────────────────────────────────
    ax.axvline(n - 1, color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=2)

    # ── 成交量 ───────────────────────────────────
    axv.bar(x[up], v[up], w, color=UP, alpha=0.85)
    axv.bar(x[~up], v[~up], w, color=DOWN, alpha=0.85)

    # ── 样式：去掉图表垃圾 ────────────────────────
    for a in (ax, axv):
        a.set_facecolor("white")
        a.grid(axis="y", color=GRID, lw=0.7)
        a.set_axisbelow(True)
        for side in ("top", "right"):
            a.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            a.spines[side].set_color("#ccd2da")
        a.tick_params(colors=MUTED, labelsize=8, length=3)
    ax.tick_params(labelbottom=False)
    axv.set_ylabel("成交量（手）", fontsize=8.5, color=MUTED)
    ax.set_ylabel("价格（元，前复权）", fontsize=8.5, color=MUTED)

    # x 轴只留 5 个日期刻度（避免挤成一团）
    ticks = np.linspace(0, n - 1, 5).astype(int)
    axv.set_xticks(ticks)
    axv.set_xticklabels(df["date"].dt.strftime("%Y-%m").iloc[ticks], fontsize=8)
    axv.xaxis.set_minor_locator(mdates.AutoDateLocator())

    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2, handlelength=1.6)
    fig.suptitle(f"{name}（{code}）日线 · {df['date'].iloc[0]:%Y-%m-%d} 至 "
                 f"{df['date'].iloc[-1]:%Y-%m-%d}", fontsize=10.5,
                 color=INK, x=0.012, ha="left", y=0.975)

    # ── caption：图外文字，回答"这张图想让用户看到什么"──
    fig.text(0.012, 0.055,
             "红色是涨、绿色是跌。竖看一根＝一天：粗的部分是开盘到收盘，上下细线是当天最高最低。",
             fontsize=8.6, color=INK, ha="left")
    fig.text(0.012, 0.018,
             "历史表现不代表未来。本图仅呈现已发生的事实，不构成买卖建议。",
             fontsize=7.6, color=MUTED, ha="left")

    fig.subplots_adjust(left=0.105, right=0.985, top=0.90, bottom=0.15)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"已生成 {out}（{out.stat().st_size / 1024:.0f} KB）")


def main() -> None:
    df = load("600519", "2024-01-01", "2025-06-30")
    print(f"{len(df)} 个交易日")
    draw("600519", "贵州茅台", df, OUT)


if __name__ == "__main__":
    main()
