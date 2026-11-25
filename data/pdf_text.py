"""PDF 文本解析：文字层抽取 → 扫描件判断 → 章节切块（带页码）。

只处理 A 股定期报告（年报/半年报/季报），章节结构固定，用正则切比 layout 模型
更可控、更可复现（同一 PDF 两次跑结果完全一致）。

fitz（PyMuPDF）惰性导入：build 期依赖（A 建库用），运行时（exe/agent）不需要。
"""
from __future__ import annotations

import re

SCAN_THRESHOLD = 50          # 平均每页字符 < 50 → 扫描件
CHUNK_SIZE = 800             # 单块目标长度（字符）
MAX_LEN = 60_000             # 单篇入库上限（约前 40 页，财务附注不入库）
SECTION_RE = re.compile(r"^\s*(第[一二三四五六七八九十百]+节|第[一二三四五六七八九十百]+章)\s*.*$")

KEEP_HINTS = ("管理层讨论", "经营情况讨论", "重要事项", "公司简介和主要财务指标")
DROP_HINTS = ("财务报告", "审计报告", "公司治理", "环境", "社会责任",
              "股份变动", "优先股", "债券", "备查文件", "释义", "独立财务顾问")


def extract_pages(pdf_bytes: bytes) -> list[str]:
    """逐页抽文字层，返回每页文本（索引 0 = 第 1 页）。"""
    import fitz                                 # noqa: PLC0415  惰性导入
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [p.get_text() for p in doc]
    doc.close()
    return pages


def extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    pages = extract_pages(pdf_bytes)
    return "".join(pages), len(pages)


def is_scanned(text: str, page_count: int) -> bool:
    if page_count <= 0:
        return True
    return len(text) / page_count < SCAN_THRESHOLD


def keep_section(heading: str) -> bool:
    """章节取舍：保留定性章节，丢纯数字章节；无标题（整篇）默认保留。"""
    if not heading:
        return True
    for h in KEEP_HINTS:
        if h in heading:
            return True
    for h in DROP_HINTS:
        if h in heading:
            return False
    return False                      # 未识别的章节默认丢弃（保守，避免噪音）


def to_chunks(pages: list[str], prefix: str) -> list[dict]:
    """逐页文本 → 分块，每块带「上下文前缀 + 章节 + 起始页码」。

    返回 [{"seq", "section", "page", "text"}]，text 已注入上下文前缀。
    两个实测坑的处理：
      1. 章节标题文字和"第X节"常分两行 → 把下一行短文本并入标题
      2. 年报开头是目录（重复一遍"第X节"）→ 从第二个「第一节」开始取
    """
    # 行 → 页码
    lines: list[tuple[str, int]] = []
    for pg, ptext in enumerate(pages, 1):
        for line in ptext.splitlines():
            lines.append((line, pg))

    # 章节标记
    markers: list[tuple[int, str, int]] = []
    for i, (line, pg) in enumerate(lines):
        if SECTION_RE.match(line) and len(line) <= 40:
            title = line.strip()
            if i + 1 < len(lines):
                nxt = lines[i + 1][0].strip()
                if 0 < len(nxt) <= 40:
                    title = f"{title} {nxt}"
            markers.append((i, title, pg))
    if not markers:
        return _chunk_body([(l, p) for l, p in lines], prefix, "", 1)

    sections: list[tuple[str, int, list[tuple[str, int]]]] = []
    for j, (idx, heading, _pg) in enumerate(markers):
        end = markers[j + 1][0] if j + 1 < len(markers) else len(lines)
        sections.append((heading, markers[j][2], lines[idx:end]))

    # 跳过目录
    first = re.match(r"第[一二三四五六七八九十百]+[节章]", sections[0][0])
    if first:
        key = first.group(0)
        seen = [k for k, (h, _, _) in enumerate(sections) if h.startswith(key)]
        if len(seen) >= 2:
            sections = sections[seen[1]:]

    # 逐节分块（按节粒度受 MAX_LEN 约束，避免单篇过大）
    chunks: list[dict] = []
    total = 0
    for heading, start_page, body_lines in sections:
        if not keep_section(heading):
            continue
        sec_chunks = _chunk_body(body_lines, prefix, heading, start_page)
        sec_len = sum(len(c["text"]) for c in sec_chunks)
        if total + sec_len > MAX_LEN and chunks:
            break                        # 预算用尽，后面的节不再入
        chunks += sec_chunks
        total += sec_len
    # 全局连续编号
    for i, c in enumerate(chunks):
        c["seq"] = i
    return chunks


def _chunk_body(lines: list[tuple[str, int]], prefix: str,
                heading: str, start_page: int) -> list[dict]:
    """把一节的行按段落聚合、切块。"""
    paras: list[tuple[str, int]] = []
    buf, buf_pg = "", start_page
    for line, pg in lines:
        s = line.strip()
        if not s:
            if buf:
                paras.append((buf, buf_pg))
                buf = ""
            continue
        if not buf:
            buf_pg = pg
        buf = (buf + s) if buf else s
    if buf:
        paras.append((buf, buf_pg))

    out: list[dict] = []
    seq = 0
    acc, acc_pg = "", start_page
    for text, pg in paras:
        if len(acc) + len(text) > CHUNK_SIZE and acc:
            out.append({"seq": seq, "section": heading, "page": acc_pg,
                        "text": f"{prefix}{heading}】\n{acc}"})
            seq += 1
            acc, acc_pg = text, pg
        else:
            if not acc:
                acc_pg = pg
            acc = (acc + "\n" + text) if acc else text
    if acc:
        out.append({"seq": seq, "section": heading, "page": acc_pg,
                    "text": f"{prefix}{heading}】\n{acc}"})
    return out
