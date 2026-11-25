"""按需补公告正文（巨潮 PDF）：T1 财报类 + T2 重大事项/增减持/业绩预告。

与 fill_content.py（东财纯文本）的分工：
  * 短公告（减持/回购/分红）→ 东财即可，5k 截断不影响
  * 长财报（年报/半年报/季报）→ 巨潮 PDF，全文 + 带页码
本脚本走巨潮：下载 PDF → 抽文字 → 按章节切块 → 存 doc_chunks + chunks_fts。

用法
----
python -m scripts.fill_content_cninfo --limit 5 --delay 2   # 小批试跑
python -m scripts.fill_content_cninfo --codes 600519         # 只补一只
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time

from data import chunks as chunks_store
from data import db
from data.pdf_text import extract_pages, extract_text, is_scanned, to_chunks
from data.sources import em_cninfo

DELAY = 2.0
T2_KEYWORDS = ("减持", "增持", "质押", "诉讼", "处罚", "问询", "停牌", "复牌",
               "收购", "重组", "关联交易", "业绩预告", "业绩快报", "中标", "重大合同")


def _norm(title: str) -> str:
    """标题规范化：去公司前缀、空白；用于东财 art_code ↔ 巨潮标题匹配。"""
    t = (title or "").strip()
    if ":" in t:
        t = t.split(":", 1)[1].strip()
    return re.sub(r"\s+", "", t)


def _period_label(title: str, doc_type: str) -> str:
    m = re.search(r"(20\d{2})年", title)
    year = m.group(1) if m else ""
    if "半年度" in title:
        return f"{year}半年报"
    if "第一季度" in title or "一季" in title:
        return f"{year}一季报"
    if "第三季度" in title or "三季" in title:
        return f"{year}三季报"
    if "年度报告" in title or "年报" in title:
        return f"{year}年报"
    if "权益分派" in title or "分红" in title:
        return f"{year}分红"
    return f"{year}{doc_type}"


def _ensure_schema() -> None:
    with db.connect(readonly=False) as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(announcements)")}
        for col in ("pdf_url", "page_count", "parse_status"):
            if col not in cols:
                c.execute(f"ALTER TABLE announcements ADD COLUMN {col} TEXT")
        c.executescript((__import__("pathlib").Path("data/migrations/003_chunks.sql"))
                        .read_text(encoding="utf-8"))
        c.commit()


def targets(codes: list[str] | None, limit: int, force: bool = False) -> list[dict]:
    """T1（财报/分红）+ T2（重大事项等）。默认只选没正文的；--force 重跑全部。"""
    sql = ("SELECT art_code, code, title, notice_date, doc_type FROM announcements"
           " WHERE (doc_type IN ('年报','半年报','季报','分红')"
           " OR (doc_type = '其他' AND (" +
           " OR ".join("title LIKE ?" for _ in T2_KEYWORDS) + ")))")
    args: list = [f"%{k}%" for k in T2_KEYWORDS]
    if not force:
        sql = sql.replace(" WHERE ", " WHERE content_len = 0 AND ", 1)
    if codes:
        sql += " AND code IN (%s)" % ",".join("?" * len(codes))
        args += list(codes)
    sql += " ORDER BY notice_date DESC LIMIT ?"
    args.append(limit * 4)
    with db.connect() as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    return rows[:limit]


def _company(code: str) -> str:
    with db.connect() as c:
        r = c.execute("SELECT name FROM instruments WHERE code=?", (code,)).fetchone()
    return r["name"] if r else code


def fill_one(sess, a: dict, cninfo_items: list[dict]) -> str:
    """补一条公告正文，返回状态描述。"""
    want = _norm(a["title"])
    # 标题匹配：规范化后相等，且排除更正/修订版
    hit = next((x for x in cninfo_items
                if _norm(x["title"]) == want and "更正" not in x["title"]
                and "修订" not in x["title"]), None)
    if not hit:
        chunks_store.mark_failed(art_code=a["art_code"], parse_status="no_match")
        return "no_match"

    pdf = em_cninfo.fetch_pdf(sess, hit["adjunct_url"])
    text, pages = extract_text(pdf)
    if is_scanned(text, pages):
        chunks_store.mark_failed(art_code=a["art_code"], parse_status="no_text_layer")
        return "scanned"

    company = _company(a["code"])
    label = _period_label(a["title"], a["doc_type"])
    prefix = f"【{company}·{label}·"
    chunk_list = to_chunks(extract_pages(pdf), prefix)
    if not chunk_list:
        chunks_store.mark_failed(art_code=a["art_code"], parse_status="no_content")
        return "empty"

    chunks_store.save_fulltext(
        art_code=a["art_code"], code=a["code"], company=company,
        report_period=label, publish_date=a["notice_date"], content=text[:60_000],
        page_count=pages, pdf_url=hit["adjunct_url"],
        pdf_sha256=hashlib.sha256(pdf).hexdigest(),
        chunks=chunk_list)
    return f"ok:{len(chunk_list)}chunks"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--delay", type=float, default=DELAY)
    ap.add_argument("--codes", nargs="*", default=None)
    ap.add_argument("--force", action="store_true", help="重跑已入库的（重解析）")
    args = ap.parse_args()

    _ensure_schema()
    sess = em_cninfo._session()
    rows = targets(args.codes, args.limit, args.force)
    if not rows:
        print("没有待补的 T1/T2 公告")
        return 0
    print(f"本批 {len(rows)} 条，间隔 {args.delay}s")

    ok = fail = 0
    list_cache: dict[str, list[dict]] = {}
    for i, a in enumerate(rows, 1):
        code = a["code"]
        if code not in list_cache:
            try:
                list_cache[code] = em_cninfo.fetch_list(
                    sess, code, "2023-01-01", "2025-06-30")
            except Exception as e:                    # noqa: BLE001
                print(f"  [{i}] 拉列表失败 {code}: {type(e).__name__}")
                list_cache[code] = []
        try:
            status = fill_one(sess, a, list_cache[code])
            ok += 1 if status.startswith("ok") else 0
            fail += 0 if status.startswith("ok") else 1
            print(f"  [{i}/{len(rows)}] {status:<14} {a['title'][:38]}")
        except Exception as e:                        # noqa: BLE001
            fail += 1
            print(f"  [{i}/{len(rows)}] ✗ {type(e).__name__} {a['title'][:38]}")
            if type(e).__name__ in ("ConnectionError", "RemoteDisconnected"):
                print("  ⚠️ 疑似限流，停止。冷却后重跑。")
                break
        time.sleep(args.delay)

    print(f"\n本批：成功 {ok}，未命中/失败 {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
