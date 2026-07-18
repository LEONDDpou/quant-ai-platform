"""实时行情服务（需求 1）。

职责：
  * 聚合多数据源（经 FailoverOrchestrator）获取实时行情；
  * 维护进程内「整表共享快照」，供 REST 与 WebSocket 推送共用（每刷新周期仅一次批量请求）；
  * 数据异常检测（价格/涨跌幅越界、负值）——异常数据剔除并告警，避免脏数据进入策略；
  * 暴露数据源健康报告。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..core.config import MarketSettings, settings as default_settings
from ..sources.base import Quote
from ..sources.failover import FailoverOrchestrator, build_orchestrator

logger = logging.getLogger(__name__)


def validate_quote(q: Quote) -> bool:
    """数据异常检测（需求 8）。A 股涨跌停通常为 ±10%（科创板/创业板 ±20%）。"""
    if q.price <= 0:
        return False
    if not (-15.0 <= q.change_pct <= 15.0):
        return False
    if q.volume < 0 or q.amount < 0:
        return False
    return True


class QuoteService:
    def __init__(self, settings: MarketSettings | None = None):
        self.settings = settings or default_settings
        self.orchestrator = build_orchestrator(self.settings)
        self.snapshot: dict[str, Quote] = {}
        self._lock = asyncio.Lock()
        self.last_refresh_ts: float = 0.0

    async def refresh(self, codes: list[str]) -> dict[str, Quote]:
        """拉取并校验行情，更新共享快照，返回清洗后的行情。"""
        raw = await self.orchestrator.get_quotes(codes)
        clean: dict[str, Quote] = {}
        anomalies: list[str] = []
        for c, q in raw.items():
            if validate_quote(q):
                clean[c] = q
            else:
                anomalies.append(c)
        if anomalies:
            logger.warning("[quote_svc] 剔除异常行情 %d 只: %s", len(anomalies), anomalies[:10])
        async with self._lock:
            self.snapshot.update(clean)
            self.last_refresh_ts = __import__("time").time()
        return clean

    async def get_snapshot(self, codes: Optional[list[str]] = None) -> dict[str, Quote]:
        async with self._lock:
            if codes:
                return {c: self.snapshot[c] for c in codes if c in self.snapshot}
            return dict(self.snapshot)

    def source_health(self) -> list[dict]:
        return self.orchestrator.health_report()
