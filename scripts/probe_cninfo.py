"""S1 探针：跑 5 篇年报，验证巨潮容忍度 + PDF 解析质量 + 章节切分。

用法：python -m scripts.probe_cninfo
产出：frontend/shots/ 之外不落任何文件；只打印质量报告。
"""
from __future__ import annotations

import time

from data.pdf_text import extract_text, is_scanned, keep_section, split_sections
from data.sources import em_cninfo

CODES = ["600519", "000001", "600036", "000333", "002415"]
DELAY = 2.0


def pick_annual(items: list[dict], year: str = "2024") -> dict | None:
    """在巨潮列表里挑「正文年报」（排除摘要/英文/半年度）。"""
    for it in items:
        t = it["title"]
        if f"{year}年年度报告" in t and "摘要" not in t and "英文" not in t:
            return it
    return None


def main() -> None:
    sess = em_cninfo._session()
    ok, fail = 0, 0
    print(f"间隔 {DELAY}s，逐篇下载……\n")
    for i, code in enumerate(CODES, 1):
        print(f"── [{i}/{len(CODES)}] {code} ──")
        try:
            items = em_cninfo.fetch_list(sess, code, "2024-01-01", "2025-06-30")
            annual = pick_annual(items)
            if not annual:
                print("  ✗ 没找到 2024 年报（列表 %d 条）" % len(items))
                fail += 1
                time.sleep(DELAY)
                continue
            pdf = em_cninfo.fetch_pdf(sess, annual["adjunct_url"])
            text, pages = extract_text(pdf)
            scanned = is_scanned(text, pages)
            secs = split_sections(text)
            keep = [h for h, _ in secs if keep_section(h)]
            drop = [h for h, _ in secs if not keep_section(h)]
            print("  %s" % annual["title"][:44])
            print("  PDF %.1f MB，%d 页，抽出 %d 字%s" % (
                len(pdf) / 1e6, pages, len(text), "（⚠️扫描件）" if scanned else ""))
            print("  识别章节 %d 个：保留 %d / 丢弃 %d" % (len(secs), len(keep), len(drop)))
            for h in keep[:4]:
                print("    ✓ 保留", h)
            ok += 1
        except Exception as e:                       # noqa: BLE001
            print("  ✗ %s: %s" % (type(e).__name__, str(e)[:100]))
            fail += 1
            if "Connection" in type(e).__name__ or "Remote" in type(e).__name__:
                print("  ⚠️ 疑似限流，建议停下冷却")
                break
        time.sleep(DELAY)

    print("\n=== S1 结论 ===")
    print("  成功 %d / 失败 %d" % (ok, fail))


if __name__ == "__main__":
    main()
