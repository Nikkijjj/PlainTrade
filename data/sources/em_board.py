"""行业板块：列表 / 历史行情 / 成分股。实测可用（2026-11）。

板块 secid 形如 90.BK0475，历史行情直接复用 em_quote.fetch_kline。
"""
from __future__ import annotations

import requests

from data.sources.base import get_json

CLIST = "https://push2.eastmoney.com/api/qt/clist/get"
FS_INDUSTRY = "m:90+t:2"          # 行业板块；概念板块是 m:90+t:3


def _clist(sess: requests.Session, fs: str, fields: str, pz: int, tag: str,
           max_pages: int = 1) -> list[dict]:
    """东财 clist 单页最多返回 100 条，pz 传再大也会被截断 -> 必须翻页。"""
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        js = get_json(sess, CLIST, {
            "pn": str(page), "pz": str(pz), "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3", "fs": fs, "fields": fields,
        }, tag=tag)
        data = js.get("data") or {}
        diff = data.get("diff") or []
        out.extend(diff)
        total = int(data.get("total") or 0)
        if len(out) >= total or not diff:
            break
    return out


def fetch_board_list(sess: requests.Session) -> list[dict]:
    """全部行业板块（实测约 496 个，5 页）。[:{board_code, board_name, pct_chg}]"""
    return [{"board_code": it.get("f12"), "board_name": it.get("f14"),
             "pct_chg": it.get("f3")}
            for it in _clist(sess, FS_INDUSTRY, "f12,f14,f3", 100,
                             "board_list", max_pages=8)]


def fetch_board_members(sess: requests.Session, board_code: str) -> list[dict]:
    """板块成分股：[{code, name}]（超过 100 只的板块会自动翻页）"""
    return [{"code": it.get("f12"), "name": it.get("f14")}
            for it in _clist(sess, "b:" + board_code, "f12,f14", 100,
                             "board_members", max_pages=6)]


def secid_of_board(board_code: str) -> str:
    return "90." + board_code
