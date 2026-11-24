"""FTS5 索引的**体检与重建入口**。

归属约定（重要）
----------------
真正写索引的代码在 `data/etl.py::build_fts` —— 因为 FTS 表和公告表在同一个库里，
而 data 层不能被 research 反向依赖。所以这里只做两件事：
  * build_index()  委托给 data 层（保留原接口，谁调用都还在）
  * index_stats()  读库做体检（文档数、空正文数、覆盖率）

不要把建索引的 SQL 再抄一份到这里，否则入库与体检会用两套分词。
"""
from __future__ import annotations



def build_index() -> int:
    """重建全量索引，返回写入的文档数（委托 data 层，实现唯一）。"""
    from data.indexer import build_fts
    return build_fts()


def index_stats() -> dict:
    """索引体检：索引了多少、其中多少是真正文。"""
    from data.indexer import index_stats as _stats
    return _stats()


def main() -> None:
    print("索引体检：", index_stats())
    print("重建索引：", build_index(), "篇")
    print("重建后：", index_stats())


if __name__ == "__main__":
    main()
