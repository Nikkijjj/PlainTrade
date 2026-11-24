"""FTS5 索引构建。

为什么单独一个模块：`etl.py` 已经到 200 行上限，而索引构建和"抓取入库"是
两件事——前者可反复重跑（幂等），后者依赖网络。分开放也便于单独调。

正文缺失时退回索引**标题**：东财正文接口会限流（见 etl 模块头），但检索能力
不能因此完全不可用——标题里已含"年度报告/减持/回购"这类关键信息。
"""
from __future__ import annotations

from data import db
from data.text import tokenize


def build_fts() -> int:
    """把公告写入 docs_fts（先清后插，幂等）。返回文档数。"""
    with db.connect(readonly=False) as c:
        c.execute("DELETE FROM docs_fts")
        rows = c.execute(
            "SELECT art_code, code, title,"
            " CASE WHEN content_len > 0 THEN content ELSE title END AS body"
            " FROM announcements").fetchall()
        c.executemany(
            "INSERT INTO docs_fts(doc_id,source,code,title,body) VALUES (?,?,?,?,?)",
            [(r["art_code"], "announcement", r["code"], r["title"],
              tokenize(r["body"] or "")) for r in rows])
        c.commit()
        return len(rows)


def index_stats() -> dict:
    """索引体检：索引了多少、其中多少是真正文。"""
    with db.connect() as c:
        docs = c.execute("SELECT count(*) FROM docs_fts").fetchone()[0]
        total = c.execute("SELECT count(*) FROM announcements").fetchone()[0]
        with_body = c.execute(
            "SELECT count(*) FROM announcements WHERE content_len > 0").fetchone()[0]
    return {"indexed": docs, "announcements": total, "with_body": with_body,
            "title_only": max(0, docs - with_body)}
