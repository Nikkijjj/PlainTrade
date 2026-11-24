"""生成演示用图表 PNG（base64 内联到前端），验证「后端渲染 → base64 → img」这条链路。

真上线时由 adapt/render.py 用 matplotlib 产出；这里用 PIL 只是为了在没有
matplotlib 的环境里也能看到界面效果。中文必须显式指定字体，否则会画成方框。
"""
from __future__ import annotations

import base64
import json
import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("frontend/mock_images.js")
W, H = 640, 220
GREEN_DARK, GREEN_LIGHT, INK, GRID, MUTED = (
    (15, 123, 63), (143, 195, 166), (31, 59, 99), (238, 241, 245), (154, 163, 178))

FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",      # 黑体
    "C:/Windows/Fonts/simsun.ttc",      # 宋体
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)
F12 = None


def init_font() -> None:
    """加载中文字体。PIL 默认位图字体没有 CJK 字形，会画成方框。"""
    global F12
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                F12 = ImageFont.truetype(path, 13)
                return
            except OSError:
                continue
    F12 = ImageFont.load_default()


def canvas():
    img = Image.new("RGB", (W, H), "white")
    return img, ImageDraw.Draw(img)


def _png_data_url(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def bars() -> str:
    """板块跌幅柱状图。A 股习惯：跌幅用绿。"""
    img, d = canvas()
    data = [("半导体", -6.8), ("软件服务", -6.1), ("通信设备", -5.4),
            ("电子元件", -5.0), ("医药生物", -2.1), ("食品饮料", -0.8)]
    top, bottom, left = 22, H - 42, 46
    d.line([(left, top), (W - 12, top)], fill=(213, 219, 228))
    for v in (-2, -4, -6, -8):
        y = top + (v / -8) * (bottom - top)
        d.line([(left, y), (W - 12, y)], fill=GRID)
        d.text((left - 32, y - 7), f"{v}%", fill=MUTED, font=F12)
    slot = (W - 12 - left) / len(data)
    for i, (name, v) in enumerate(data):
        x = left + i * slot + 9
        w = slot - 18
        h = abs(v / -8) * (bottom - top)
        d.rectangle([x, top, x + w, top + h],
                    fill=GREEN_DARK if i == 0 else GREEN_LIGHT)
        d.text((x + 2, top + h + 5), f"{v}%", fill=(20, 96, 58), font=F12)
        d.text((x - 2, bottom + 8), name, fill=(75, 85, 99), font=F12)
    return _png_data_url(img)


def drawdown() -> str:
    """回撤曲线（全部为负，用绿）。"""
    img, d = canvas()
    left, top, bottom = 48, 20, H - 30
    d.line([(left, top), (W - 10, top)], fill=(213, 219, 228))
    for v in (-10, -20, -30):
        y = top + (v / -30) * (bottom - top)
        d.line([(left, y), (W - 10, y)], fill=GRID)
        d.text((left - 36, y - 7), f"{v}%", fill=MUTED, font=F12)
    pts = []
    n = 120
    for i in range(n):
        t = i / (n - 1)
        dip = -0.28 * math.exp(-((t - 0.60) / 0.19) ** 2)
        v = min(0.0, dip - 0.013 * math.sin(t * 24))
        pts.append((left + t * (W - 10 - left), top + (v / -0.30) * (bottom - top)))
    d.line(pts, fill=GREEN_DARK, width=2)
    lx, ly = max(pts, key=lambda p: p[1])          # 屏幕 y 越大越靠下 = 最深点
    d.line([(lx, top), (lx, ly)], fill=(11, 92, 48))
    d.ellipse([lx - 3, ly - 3, lx + 3, ly + 3], fill=GREEN_DARK)
    d.text((lx + 8, ly - 18), "最深 −28%", fill=(11, 92, 48), font=F12)
    d.text((left, H - 18), "2024-06", fill=MUTED, font=F12)
    d.text((W - 62, H - 18), "2025-06", fill=MUTED, font=F12)
    return _png_data_url(img)


def main() -> None:
    init_font()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"bars": bars(), "drawdown": drawdown()}
    OUT.write_text("window.__IMAGES__ = " + json.dumps(payload) + ";\n", encoding="utf-8")
    print(f"已生成 {OUT}（{OUT.stat().st_size / 1024:.0f} KB，字体={'ok' if F12 else 'fallback'}）")


if __name__ == "__main__":
    main()