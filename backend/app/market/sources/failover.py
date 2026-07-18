"""多数据源故障切换编排器。

核心职责（需求 8：异常处理 / 自动切换）：
  * 按优先级依次尝试数据源；某源失败自动切到下一个；
  * 每源配独立熔断器（连续失败达到阈值即熔断，冷却后_half-open_探测）；
  * 全局令牌桶限流，保护下游行情网关；
  * 共享缓存 + stale-while-revalidate：缓存新鲜时直接返回，过期后再异步刷新；
    全部源不可用时回退到最近一次成功数据（serve-stale），保证前端不空屏。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from ..core.config import MarketSettings, settings as default_settings
from ..core.exceptions import SourceUnavailableError
from ..core.resilience import CircuitBreaker, RateLimiter, retry
from .base import Quote, QuoteSource
from .akshare import AkShareSource
from .eastmoney import EastMoneySource
from .sina import SinaSource
from .tencent import TencentSource

logger = logging.getLogger(__name__)

# 源名 -> 构造器（便于按 settings.source_priority 动态组装）
_SOURCE_FACTORIES = {
    "tencent": TencentSource,
    "eastmoney": EastMoneySource,
    "sina": SinaSource,
    "akshare": AkShareSource,
}


class FailoverOrchestrator:
    def __init__(self, sources: list[QuoteSource], settings: MarketSettings):
        # 按优先级排序（settings.source_priority 决定尝试次序）
        self.sources: list[QuoteSource] = sorted(
            sources, key=lambda s: self._priority_index(s.name, settings)
        )
        self.settings = settings
        self._cb: dict[str, CircuitBreaker] = {
            s.name: CircuitBreaker(s.name, settings.cb_fail_threshold, settings.cb_cooldown)
            for s in self.sources
        }
        self._limiter = RateLimiter(settings.rate_limit_per_sec)
        self._cache: dict[str, tuple[float, Quote]] = {}
        self._cache_ttl = float(settings.refresh_rate)
        self.last_source: str = ""
        self.last_error: str = ""
        self._lock = asyncio.Lock()

    @staticmethod
    def _priority_index(name: str, settings: MarketSettings) -> int:
        try:
            return settings.source_priority.index(name)
        except ValueError:
            return 999

    def _cache_get(self, code: str, now: float) -> Optional[Quote]:
        item = self._cache.get(code)
        if item and (now - item[0]) < self._cache_ttl:
            return item[1]
        return None

    async def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        codes = [c for c in codes if c]
        if not codes:
            return {}
        now = time.time()

        # 1) 命中新鲜缓存的直接返回（无需打网络）
        result: dict[str, Quote] = {}
        missing: list[str] = []
        for c in codes:
            q = self._cache_get(c, now)
            if q:
                result[c] = q
            else:
                missing.append(c)
        if not missing:
            return result

        # 2) 依次尝试数据源（故障切换）
        tried: list[str] = []
        async with self._lock:
            for src in self.sources:
                if not src.available:
                    continue
                cb = self._cb[src.name]
                if not cb.allow():
                    logger.info("[failover] 源 %s 熔断中，跳过", src.name)
                    tried.append(f"{src.name}(cb_open)")
                    continue
                tried.append(src.name)
                try:
                    await self._limiter.acquire()
                    fetched = await retry(
                        lambda: src.fetch_quotes(missing),
                        attempts=self.settings.source_retries,
                        base_delay=0.3,
                    )
                    cb.record_success()
                    self.last_source = src.name
                    self.last_error = ""
                    for c, q in fetched.items():
                        self._cache[c] = (now, q)
                        result[c] = q
                    # 部分源可能只返回子集；剩余缺失的用陈旧缓存兜底
                    for c in missing:
                        if c not in result:
                            stale = self._cache.get(c)
                            if stale:
                                result[c] = stale[1]
                    return result
                except Exception as e:  # noqa: BLE001
                    cb.record_failure()
                    self.last_error = f"{src.name}: {e}"
                    logger.warning("[failover] 源 %s 失败，切换下一源: %s", src.name, e)

        # 3) 全部源失败：尽量用陈旧缓存兜底
        if not result:
            stale_hits = {c: v[1] for c in codes if (v := self._cache.get(c))}
            if stale_hits:
                logger.warning("[failover] 全部源不可用，返回陈旧缓存 %d 只", len(stale_hits))
                return stale_hits
            raise SourceUnavailableError("所有行情数据源均不可用", tried=tried)
        logger.warning("[failover] 部分源失败，返回可用子集 %d/%d", len(result), len(codes))
        return result

    def health_report(self) -> list[dict]:
        out = []
        for s in self.sources:
            out.append({
                "name": s.name,
                "available": s.available,
                "circuit": self._cb[s.name].state.value,
                "lastUsed": self.last_source == s.name,
            })
        return out


def build_orchestrator(settings: MarketSettings | None = None) -> FailoverOrchestrator:
    """按配置组装默认编排器（腾讯 → 东财 → 新浪 → AkShare）。"""
    settings = settings or default_settings
    sources: list[QuoteSource] = []
    for name in settings.source_priority:
        factory = _SOURCE_FACTORIES.get(name)
        if factory is None:
            logger.warning("[failover] 未知数据源：%s（跳过）", name)
            continue
        try:
            sources.append(factory())
        except Exception as e:  # noqa: BLE001
            logger.warning("[failover] 源 %s 实例化失败: %s", name, e)
    if not sources:
        raise RuntimeError("未配置任何可用数据源")
    return FailoverOrchestrator(sources, settings)
