-- 002: 事件场景要画「板块当日涨跌幅」柱状图，原 schema 只有 boards/board_members，缺行情表。
CREATE TABLE IF NOT EXISTS board_daily (
  board_code TEXT NOT NULL, date TEXT NOT NULL,
  close REAL, pct_chg REAL, amount REAL,
  PRIMARY KEY (board_code, date));
CREATE INDEX IF NOT EXISTS idx_bd ON board_daily(date);
