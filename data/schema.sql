PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS instruments (
  code TEXT PRIMARY KEY, name TEXT NOT NULL, board TEXT, industry TEXT,
  total_shares REAL, shares_asof TEXT, updated_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS prices_daily (
  code TEXT NOT NULL, date TEXT NOT NULL,
  adj TEXT NOT NULL CHECK (adj IN ('hfq','qfq')),
  open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL,
  PRIMARY KEY (code, date, adj));

CREATE TABLE IF NOT EXISTS index_daily (
  secid TEXT NOT NULL, name TEXT, date TEXT NOT NULL,
  close REAL, pct_chg REAL, amount REAL, PRIMARY KEY (secid, date));

CREATE TABLE IF NOT EXISTS boards (
  board_code TEXT PRIMARY KEY, board_name TEXT NOT NULL, snapshot_date TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS board_daily (
  board_code TEXT NOT NULL, date TEXT NOT NULL,
  close REAL, pct_chg REAL, amount REAL,
  PRIMARY KEY (board_code, date));
CREATE INDEX IF NOT EXISTS idx_bd ON board_daily(date);

CREATE TABLE IF NOT EXISTS board_members (
  board_code TEXT NOT NULL, code TEXT NOT NULL, snapshot_date TEXT NOT NULL,
  PRIMARY KEY (board_code, code, snapshot_date));

CREATE TABLE IF NOT EXISTS financials (
  code TEXT NOT NULL, report_period TEXT NOT NULL, announce_date TEXT,
  item TEXT NOT NULL, value REAL, unit TEXT,
  PRIMARY KEY (code, report_period, item));
CREATE INDEX IF NOT EXISTS idx_fin ON financials(code, announce_date);

CREATE TABLE IF NOT EXISTS announcements (
  art_code TEXT PRIMARY KEY, code TEXT NOT NULL, title TEXT NOT NULL,
  notice_date TEXT NOT NULL, publish_time TEXT NOT NULL, doc_type TEXT, url TEXT,
  content TEXT, content_len INTEGER, ingested_at TEXT NOT NULL,
  pdf_url TEXT, page_count INTEGER, parse_status TEXT);
CREATE INDEX IF NOT EXISTS idx_ann ON announcements(code, publish_time);

-- 公告正文（巨潮 PDF）：文档级元数据 + 分块
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

CREATE TABLE IF NOT EXISTS news (
  url TEXT PRIMARY KEY, time TEXT NOT NULL, title TEXT NOT NULL, summary TEXT,
  media TEXT, code TEXT, image TEXT, column_id TEXT, ingested_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_news ON news(time);

CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
  doc_id UNINDEXED, source, code, title, body, tokenize='unicode61');

CREATE TABLE IF NOT EXISTS ingest_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, dataset TEXT NOT NULL, run_at TEXT NOT NULL,
  rows INTEGER, min_date TEXT, max_date TEXT, status TEXT, meta_json TEXT);

CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT);
INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', '1');