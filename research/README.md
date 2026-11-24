# research/
职责：检索公告正文（FTS5 + jieba），并提供索引体检。
禁止：直接访问网络；import agents/pipeline/ui。
接口：index.build_index() / index.index_stats() / retrieve.search(query, as_of, k)

注：写索引的实现唯一在 `data/etl.py::build_fts`（FTS 表与公告表同库，且 data 不可反向依赖 research）。
