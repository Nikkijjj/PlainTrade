"""数据源共用 HTTP 层：会话、限速、重试、原始响应落盘。"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

from config.settings import settings

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    return s


def _raw_path(tag: str, key: str, ext: str) -> Path:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    d = Path(settings.raw_dir) / tag
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.{ext}"


def get_json(sess: requests.Session, url: str, params: dict, *, tag: str,
             retries: int = 3, timeout: int = 20, save_raw: bool = True) -> dict:
    last = None
    for i in range(retries):
        try:
            r = sess.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            js = r.json()
            if save_raw:
                key = url + json.dumps(params, sort_keys=True)
                _raw_path(tag, key, "json").write_text(
                    json.dumps(js, ensure_ascii=False), encoding="utf-8")
            return js
        except Exception as e:
            last = e
            time.sleep(0.6 * (2 ** i))
    raise RuntimeError(f"{tag} 请求失败（重试 {retries} 次）：{last}")