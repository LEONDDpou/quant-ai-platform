"""市场模块集中配置（pydantic-settings）。

所有可配置项通过环境变量注入，前缀 ``MARKET_``，例如：
  MARKET_REFRESH_RATE=3
  MARKET_DB_URL=postgresql+asyncpg://user:pass@localhost:5432/quant
  MARKET_SOURCE_ORDER=tencent,eastmoney,sina,akshare

本地开发默认使用 SQLite(async) 以便零依赖跑通；生产用 docker-compose 起 PostgreSQL。
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MARKET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 刷新频率（秒）：支持 1 / 3 / 5 可配置 ----
    refresh_rate: int = 3

    # ---- 数据库连接（异步 SQLAlchemy）----
    # 本地开发：sqlite+aiosqlite:///./market.db
    # 生产：    postgresql+asyncpg://user:pass@host:5432/quant
    db_url: str = "sqlite+aiosqlite:///./market.db"

    # ---- 数据源与故障切换 ----
    # 逗号分隔的源优先级（低优先级在前会被优先尝试，见 FailoverOrchestrator）
    source_order: str = "tencent,eastmoney,sina,akshare"
    source_timeout: float = 8.0          # 单源单次请求超时（秒）
    source_retries: int = 2              # 单源重试次数
    source_health_ttl: float = 60.0      # 源健康状态缓存时间（秒）

    # ---- 熔断 / 限流（可靠性原语）----
    cb_fail_threshold: int = 5           # 连续失败达到此值则熔断
    cb_cooldown: float = 30.0            # 熔断后冷却时间（秒）
    rate_limit_per_sec: int = 10         # 对外行情拉取全局限速（次/秒）

    # ---- 网络 ----
    # 本沙箱经代理的 HTTPS 握手失败、HTTP 被 502，故默认绕过环境代理直连。
    trust_env: bool = False

    # ---- 持久化 ----
    persist_batch_size: int = 200        # 批量写入阈值
    persist_interval: float = 5.0        # 落库周期（秒）

    # ---- 默认关注池（用于预热 / 演示）----
    default_watchlist: str = "sh000001,sz399001,sh000300,600519,sz000858,600036"

    @property
    def source_priority(self) -> list[str]:
        return [s.strip().lower() for s in self.source_order.split(",") if s.strip()]

    @property
    def watchlist(self) -> list[str]:
        return [c.strip() for c in self.default_watchlist.split(",") if c.strip()]


# 全局单例（模块加载时构建一次）
settings = MarketSettings()
