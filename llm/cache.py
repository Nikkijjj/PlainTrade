"""全链路缓存：同 (task, code, as_of, prompt_hash, model) 直接复用。"""
from __future__ import annotations

import hashlib


def key(*parts: object) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]