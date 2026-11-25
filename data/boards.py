"""板块数据装载：板块列表 → 相关板块行情 → 成分股。

为什么要板块
-----------
① 事件场景（"今天科技股跌这么多怎么了"）需要"哪些板块在跌"的柱状图数据；
② 个股归因时要说"是行业性的还是它自己有问题"，需要同行对比。

选板策略：优先挑我们标的所属行业的板块；不足再按当日涨跌幅绝对值补足，
保证事件场景永远有数据可画。

快照语义：boards / board_members 带 snapshot_date（成分会变，不能当历史）；
board_daily 是行情，按 (board_code, date) 存，可做 as-of。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from data import db
from data.etl import DELAY
from data.sources import em_board, em_quote

CST = timezone(timedelta(hours=8))
MIN_BOARDS = 4
MAX_BOARDS = 8
_SUFFIXES = ("Ⅱ", "Ⅲ", "II", "III")


def _today() -> str:
    return datetime.now(CST).date().isoformat()


def _norm(name: str) -> str:
    """'白酒Ⅱ' -> '白酒'；对齐行业名与板块名。"""
    s = (name or "").strip()
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s.strip()


def _match(all_boards: list[dict], industries: set[str]) -> list[dict]:
    """行业名 → 板块，按"精确 > 前缀 > 包含"三档优先级匹配。

    为什么要分档：双向包含会把「电池」错配到「燃料电池」。
    所以只允许 板块名 以 行业名 开头/结尾，且排除「其他XX」这类兜底板块。
    """
    picked: list[dict] = []
    seen: set[str] = set()        # 已选板的 board_code
    seen_names: set[str] = set()  # 已选板的规范化名称（去重用）

    def add(b: dict) -> None:
        """按 board_code 和规范化名称双重去重。

        东财同时存在「银行」和「银行Ⅱ」这类同成分板块（成分股票完全相同、
        涨跌幅也相同）。不去重的话，事件场景的柱状图会出现两根一模一样的柱子，
        既占版面又误导（看图像是"两个板块在跌"）。
        """
        key = _norm(b["board_name"])
        if b["board_code"] in seen or key in seen_names:
            return
        picked.append(b)
        seen.add(b["board_code"])
        seen_names.add(key)

    wants = [w for w in (_norm(i) for i in industries) if w]
    # ① 精确
    for w in wants:
        for b in all_boards:
            if _norm(b["board_name"]) == w:
                add(b)
    # ② 前缀 / 后缀（"计算机设备" ⊂ "其他计算机设备" 这种要反过来判）
    for w in wants:
        for b in all_boards:
            bn = _norm(b["board_name"])
            if not bn or bn.startswith("其他"):
                continue
            if bn.startswith(w) or bn.endswith(w):
                add(b)
    # ③ 包含（仍排除「其他XX」）
    for w in wants:
        for b in all_boards:
            bn = _norm(b["board_name"])
            if not bn or bn.startswith("其他"):
                continue
            if w in bn and len(w) >= 2:
                add(b)
    return picked


def _fallback(all_boards: list[dict], exclude: set[str], need: int) -> list[dict]:
    """按当日涨跌幅绝对值挑"最热闹"的板块。"""
    rest = [b for b in all_boards if b["board_code"] not in exclude]
    rest.sort(key=lambda b: abs(float(b.get("pct_chg") or 0)), reverse=True)
    return rest[:need]


def load_boards(sess, start: str, end: str, max_boards: int = MAX_BOARDS):
    """写入 boards / board_daily / board_members，返回 (rows, start, end)。"""
    all_boards = em_board.fetch_board_list(sess)
    time.sleep(DELAY)
    if not all_boards:
        return [], start, end

    with db.connect() as c:
        industries = {r["industry"] for r in c.execute(
            "SELECT DISTINCT industry FROM instruments WHERE industry IS NOT NULL")}

    picked = _match(all_boards, industries)
    if len(picked) < MIN_BOARDS:
        picked += _fallback(all_boards, {b["board_code"] for b in picked},
                            MIN_BOARDS - len(picked))
    picked = picked[:max_boards]
    snap = _today()

    rows: list[dict] = []
    with db.connect(readonly=False) as c:
        for b in picked:
            code, name = b["board_code"], b["board_name"]
            c.execute("INSERT OR REPLACE INTO boards(board_code,board_name,snapshot_date)"
                      " VALUES (?,?,?)", (code, name, snap))
            try:
                members = em_board.fetch_board_members(sess, code)
            except Exception:                       # noqa: BLE001
                members = []
            c.executemany("INSERT OR REPLACE INTO board_members"
                          "(board_code,code,snapshot_date) VALUES (?,?,?)",
                          [(code, m["code"], snap) for m in members])
            time.sleep(DELAY)

            kl = em_quote.fetch_kline(sess, em_board.secid_of_board(code), start, end, "none")
            prev = None
            for r in kl:
                pct = None if prev in (None, 0) else round((r["close"] / prev - 1) * 100, 2)
                c.execute("INSERT OR REPLACE INTO board_daily"
                          "(board_code,date,close,pct_chg,amount) VALUES (?,?,?,?,?)",
                          (code, r["date"], r["close"], pct, r["amount"]))
                prev = r["close"]
                rows.append({"board_code": code, "board_name": name, "date": r["date"]})
            c.commit()
            time.sleep(DELAY)
    return rows, start, end


def fill_industries(sess) -> dict[str, str]:
    """把行业写回 instruments（个股 → 行业），供个股归因判断"是否行业性"。"""
    out: dict[str, str] = {}
    with db.connect() as c:
        codes = [r["code"] for r in c.execute(
            "SELECT code FROM instruments WHERE industry IS NULL")]
    if not codes:
        return out
    with db.connect(readonly=False) as c:
        for code in codes:
            try:
                m = em_quote.fetch_meta(sess, code)
            except Exception:                       # noqa: BLE001
                continue
            if m.get("industry"):
                c.execute("UPDATE instruments SET industry=? WHERE code=?",
                          (m["industry"], code))
                out[code] = m["industry"]
            time.sleep(DELAY)
        c.commit()
    return out
