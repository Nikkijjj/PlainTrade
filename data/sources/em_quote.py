"""东财行情与基础信息。实测可用。

secid：0.=深市 1.=沪市；指数如 0.399006(创业板指) 1.000001(上证)；板块 90.BK0475
fqt ：0=不复权 1=前复权 2=后复权
"""
from __future__ import annotations

import requests

from data.sources.base import get_json

KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
SNAP = "https://push2.eastmoney.com/api/qt/stock/get"


def secid_of(code: str) -> str:
    """600519 -> 1.600519 ; 000001 -> 0.000001"""
    return ("1." if code.startswith(("6", "9")) else "0.") + code


def fetch_kline(sess: requests.Session, secid: str, beg: str, end: str,
                adj: str = "hfq") -> list[dict]:
    fqt = {"none": "0", "qfq": "1", "hfq": "2"}[adj]
    js = get_json(sess, KLINE, {
        "secid": secid, "klt": "101", "fqt": fqt, "beg": beg, "end": end,
        "fields1": "f1,f2,f3,f4,f5,f6", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "lmt": "10000",
    }, tag="kline")
    data = js.get("data") or {}
    rows = []
    for line in data.get("klines") or []:
        f = line.split(",")
        rows.append({"date": f[0], "open": float(f[1]), "close": float(f[2]),
                     "high": float(f[3]), "low": float(f[4]),
                     "volume": float(f[5]), "amount": float(f[6]),
                     "name": data.get("name", "")})
    return rows


_SUFFIXES = ("Ⅱ", "Ⅲ", "II", "III")


def _clean_industry(v) -> str | None:
    """'白酒Ⅱ' -> '白酒'。罗马数字是东财的"二级行业"标记，对使用者是噪音。"""
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return s or None


def fetch_meta(sess: requests.Session, code: str) -> dict:
    """名称 / 总股本 / 流通股本 / 总市值 / 所属行业。

    行业字段实测是 **f127**（f100 在单只接口里恒为 null；f128 是地区板块，
    f129 是概念板块列表）。用它补 instruments.industry，避免遍历 496 个板块找成分。
    """
    js = get_json(sess, SNAP, {"secid": secid_of(code),
                               "fields": "f57,f58,f84,f85,f127,f116,f117"}, tag="snap")
    d = js.get("data") or {}
    return {"code": d.get("f57") or code, "name": d.get("f58") or "",
            "total_shares": d.get("f84"), "float_shares": d.get("f85"),
            "market_cap": d.get("f116"),
            "industry": _clean_industry(d.get("f127"))}
