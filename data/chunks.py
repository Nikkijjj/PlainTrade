"""公告正文（巨潮 PDF）的存储与检索。

与 docs_fts（标题级）分工：
  * docs_fts / search_docs    —— 标题级预过滤（快，全文缺失时也工作）
  * chunks_fts / search_chunks —— 证据检索唯一入口（带页码/章节，供 disclosure 引用）

save_fulltext 是 build 期写入（A 建库用）；search_chunks / read_pages 是运行时检索。
所有查询同样带 as_of 约束（与 db.py 同一条防泄漏规则）。
"""
from __future__ import annotations

from data import db
from data.text import fts_expr, tokenize


def save_fulltext(*, art_code: str, code: str, company: str, report_period: str,
                  publish_date: str, content: str, page_count: int, pdf_url: str,
                  pdf_sha256: str, chunks: list[dict], parse_status: str = "ok") -> None:
    """写 announcements.content + doc_meta + doc_chunks + chunks_fts（幂等）。"""
    with db.connect(readonly=False) as c:
        c.execute("UPDATE announcements SET content=?, content_len=?, page_count=?,"
                  " pdf_url=?, parse_status=? WHERE art_code=?",
                  (content, len(content), page_count, pdf_url, parse_status, art_code))
        c.execute("INSERT OR REPLACE INTO doc_meta"
                  "(doc_id,company,report_period,publish_date,pdf_url,page_count,"
                  " pdf_sha256,parser,parse_status) VALUES (?,?,?,?,?,?,?,?,?)",
                  (art_code, company, report_period, publish_date, pdf_url,
                   page_count, pdf_sha256, "fitz", parse_status))
        c.execute("DELETE FROM doc_chunks WHERE doc_id=?", (art_code,))
        c.execute("DELETE FROM chunks_fts WHERE doc_id=?", (art_code,))
        c.executemany("INSERT INTO doc_chunks(doc_id,seq,page,section,kind,text)"
                      " VALUES (?,?,?,?,?,?)",
                      [(art_code, ch["seq"], ch.get("page"), ch["section"],
                        "text", ch["text"]) for ch in chunks])
        c.executemany("INSERT INTO chunks_fts(doc_id,page,section,text)"
                      " VALUES (?,?,?,?)",
                      [(art_code, ch.get("page"), ch["section"], tokenize(ch["text"]))
                       for ch in chunks])
        c.commit()


def mark_failed(*, art_code: str, parse_status: str) -> None:
    """解析失败/扫描件：只打标记，正文保持标题。"""
    with db.connect(readonly=False) as c:
        c.execute("UPDATE announcements SET parse_status=? WHERE art_code=?",
                  (parse_status, art_code))
        c.commit()


def search_chunks(query: str, as_of: str, k: int = 5) -> list[dict]:
    """chunk 级检索（带 as_of 约束）。

    返回定位信息 + 原文片段。FTS 里存的是分词文本（检索用），
    原文（给人看、给引用）存在 doc_chunks.text，所以这里分两步：
      ① FTS 按 bm25 召回 (doc_id, page, section)
      ② 从 doc_chunks 取对应原文前 120 字当 snippet
    """
    sql = ("SELECT c.doc_id, c.page, c.section, bm25(chunks_fts) AS score"
           " FROM chunks_fts c JOIN announcements a ON a.art_code = c.doc_id"
           " WHERE chunks_fts MATCH ? AND a.publish_time < ?"
           " ORDER BY score LIMIT ?")
    with db.connect() as c:
        rows = c.execute(sql, (fts_expr(query), db._bound(as_of), k)).fetchall()
    out: list[dict] = []
    with db.connect() as c:
        for r in rows:
            orig = c.execute(
                "SELECT text FROM doc_chunks WHERE doc_id=? AND page=?"
                " ORDER BY seq LIMIT 1", (r["doc_id"], r["page"])).fetchone()
            out.append({"doc_id": r["doc_id"], "page": r["page"],
                        "section": r["section"], "score": r["score"],
                        "snippet": (orig["text"] if orig else "")[:140]})
    return out


def read_pages(doc_id: str, page_from: int, page_to: int | None = None) -> list[dict]:
    """读某份文档指定页码范围的分块（供 manager 引用原文细节）。"""
    sql = ("SELECT page, section, text FROM doc_chunks"
           " WHERE doc_id=? AND page >= ? ORDER BY page, seq")
    args: list = [doc_id, page_from]
    if page_to is not None:
        sql = ("SELECT page, section, text FROM doc_chunks"
               " WHERE doc_id=? AND page BETWEEN ? AND ? ORDER BY page, seq")
        args = [doc_id, page_from, page_to]
    with db.connect() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def doc_meta(doc_id: str) -> dict:
    with db.connect() as c:
        r = c.execute("SELECT * FROM doc_meta WHERE doc_id=?", (doc_id,)).fetchone()
    return dict(r) if r else {}
