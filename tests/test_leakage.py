"""最重要的测试：任何未来信息都必须被拦住。

泄漏不会报错，只会让结论变好看。所以只能靠测试拦。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from config.settings import settings
from contracts.argdoc import ArgDoc, Claim, Evidence

TMP_DIR = Path("data_files/_pytest")


# ── 契约层 ────────────────────────────────────────
def test_rejects_future_evidence() -> None:
    with pytest.raises(Exception):
        ArgDoc(task="stock_outlook", as_of="2025-01-04",
               evidence=[Evidence(id="e1", source="2025 年报", doc_type="announcement",
                                  publish_time="2025-03-20")])


def test_rejects_same_day_evidence() -> None:
    """保守时间规则：同日 20:00 发的公告，次日才可见。"""
    with pytest.raises(Exception):
        ArgDoc(task="stock_outlook", as_of="2025-01-04",
               evidence=[Evidence(id="e1", source="公告", doc_type="announcement",
                                  publish_time="2025-01-04 20:00:00")])


def test_accepts_past_evidence() -> None:
    doc = ArgDoc(task="stock_outlook", as_of="2025-01-04",
                 evidence=[Evidence(id="e1", source="年报", doc_type="report",
                                    publish_time="2024-03-15")],
                 claims=[Claim(id="c1", type="fact", text="营收增长 12%", evidence=["e1"])])
    assert doc.dangling_evidence() == []


# ── 数据层 ────────────────────────────────────────
@pytest.fixture()
def temp_db(monkeypatch):
    """临时库放在工作区内（不用系统 temp，避免受限目录权限问题）。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    dbp = TMP_DIR / "leakage.db"
    if dbp.exists():
        dbp.unlink()
    conn = sqlite3.connect(dbp)
    conn.executescript(Path("data/schema.sql").read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO announcements(art_code,code,title,notice_date,publish_time,"
        "doc_type,url,content,content_len,ingested_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [("a1", "000001", "旧公告", "2024-12-31", "2024-12-31 23:59:59",
          "其他", "", "", 0, "2026-01-01"),
         ("a2", "000001", "当天公告", "2025-01-04", "2025-01-04 23:59:59",
          "其他", "", "", 0, "2026-01-01")])
    conn.commit()
    conn.close()
    monkeypatch.setattr(settings, "db_path", dbp)
    yield dbp


def test_db_asof_excludes_same_day(temp_db) -> None:
    """决策日 2025-01-04 只能看到 12-31 那条，看不到当天那条。"""
    from data import db
    rows = db.asof_docs("000001", "2025-01-04", k=10)
    assert [r["title"] for r in rows] == ["旧公告"], "数据层发生泄漏"


def test_db_asof_includes_yesterday(temp_db) -> None:
    from data import db
    rows = db.asof_docs("000001", "2025-01-05", k=10)
    assert [r["title"] for r in rows] == ["当天公告", "旧公告"]