"""唯一的配置入口。任何模块都不许直接读 os.environ。"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 运行模式：replay=只读快照（评估用）；live=请求前增量更新（demo 用）
    mode: Literal["replay", "live"] = "replay"

    deepseek_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2000

    db_path: Path = Path("data_files/plantrade.db")
    raw_dir: Path = Path("data_files/raw")
    log_dir: Path = Path("logs")

    # 增量 TTL（秒）：live 模式下只有超过 TTL 的数据集才会真的去拉
    ttl_news_s: int = 300          # 新闻 5 分钟
    ttl_announcement_s: int = 3600  # 公告 1 小时
    ttl_price_s: int = 43200        # 行情 12 小时（收盘后一次即可）
    ttl_financial_s: int = 86400    # 财务 1 天

    debate_enabled: bool = True
    chart_enabled: bool = True
    guardrail_enabled: bool = True


settings = Settings()