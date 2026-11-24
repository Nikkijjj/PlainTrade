"""补公告正文（可断点续传）。

为什么单独一个脚本
------------------
东财正文接口会 IP 限流（连续约 50 次后 RemoteDisconnected）。所以正文不适合
和建库绑在一起跑：建库要的是"标题全量、快"；正文是"慢、可分批、可中断"。

用法
----
python -m scripts.fill_content                # 补 200 篇（默认）
python -m scripts.fill_content --limit 50     # 小批试跑
python -m scripts.fill_content --delay 2.0    # 更保守的间隔
python -m scripts.fill_content --force        # 连之前失败的也重试

设计
----
* 只处理 content_len = 0 的公告（幂等，跑多少遍都不会重复抓）
* 连续失败 N 次自动停，并打印"建议冷却多久"
* 结束后打印成功率，方便决定要不要再来一批
"""
from __future__ import annotations

import argparse
import sys
import time

from data import db
from data.sources import em_notice
from data.sources.base import session
from data.text import tokenize

MAX_CONSECUTIVE_FAIL = 6


def pending(limit: int) -> list[dict]:
    with db.connect() as c:
        rows = c.execute(
            "SELECT art_code, code, title FROM announcements"
            " WHERE content_len = 0 ORDER BY notice_date DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    with db.connect() as c:
        total = c.execute("SELECT count(*) FROM announcements").fetchone()[0]
        done = c.execute("SELECT count(*) FROM announcements WHERE content_len>0").fetchone()[0]
    return {"total": total, "with_body": done,
            "rate": round(done / total, 3) if total else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()

    before = stats()
    print(f"当前：共 {before['total']} 条，有正文 {before['with_body']} 条"
          f"（{before['rate']:.0%}）")

    rows = pending(args.limit)
    if not rows:
        print("没有待补的正文 ✓")
        return 0
    print(f"本批处理 {len(rows)} 条，间隔 {args.delay}s（预计 "
          f"{len(rows) * args.delay / 60:.1f} 分钟）")

    sess = session()
    ok = 0
    fail = 0
    consecutive = 0
    indexed: list[tuple] = []
    for i, r in enumerate(rows, 1):
        try:
            body = em_notice.fetch_content(sess, r["art_code"])
            if not body:
                raise ValueError("空正文")
            with db.connect(readonly=False) as c:
                c.execute("UPDATE announcements SET content=?, content_len=? WHERE art_code=?",
                          (body, len(body), r["art_code"]))
                c.commit()
            indexed.append((r["art_code"], r["code"], r["title"], body))
            ok += 1
            consecutive = 0
            print(f"  [{i}/{len(rows)}] ✓ {len(body):>5} 字  {r['title'][:28]}")
        except Exception as e:                            # noqa: BLE001
            fail += 1
            consecutive += 1
            print(f"  [{i}/{len(rows)}] ✗ {type(e).__name__}  {r['title'][:28]}")
            if consecutive >= MAX_CONSECUTIVE_FAIL:
                print(f"\n连续失败 {consecutive} 次，接口在限流。建议冷却 30-60 分钟后再跑。")
                break
        time.sleep(args.delay)

    if indexed:
        with db.connect(readonly=False) as c:
            c.executemany(
                "INSERT OR REPLACE INTO docs_fts(doc_id,source,code,title,body)"
                " VALUES (?,?,?,?,?)",
                [(a, "announcement", code, title, tokenize(body))
                 for a, code, title, body in indexed])
            c.commit()
        print(f"\n已把 {len(indexed)} 篇写入 FTS 索引")

    after = stats()
    print(f"本批：成功 {ok}，失败 {fail}")
    print(f"累计：有正文 {after['with_body']}/{after['total']}（{after['rate']:.0%}），"
          f"剩余 {after['total'] - after['with_body']} 条")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
