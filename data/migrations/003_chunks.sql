-- 003: 公告正文（巨潮 PDF）。新增 announcements 三列 + doc_meta + doc_chunks + chunks_fts。
-- 幂等：用 IF NOT EXISTS；列用 ALTER，靠调用方先查 PRAGMA table_info 再决定是否加。

CREATE TABLE IF NOT EXISTS doc_meta (
  doc_id TEXT PRIMARY KEY, company TEXT, report_period TEXT, publish_date TEXT,
  pdf_url TEXT, page_count INTEGER, pdf_sha256 TEXT,
  parser TEXT, parse_status TEXT);

CREATE TABLE IF NOT EXISTS doc_chunks (
  doc_id TEXT NOT NULL, seq INTEGER NOT NULL, page INTEGER,
  section TEXT, kind TEXT DEFAULT 'text', text TEXT NOT NULL,
  PRIMARY KEY (doc_id, seq));

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  doc_id UNINDEXED, page UNINDEXED, section, text, tokenize='unicode61');
