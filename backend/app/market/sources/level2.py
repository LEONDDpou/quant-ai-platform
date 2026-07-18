"""券商 Level-2 行情源扩展接口（可插拔）。

普通行情源（腾讯/东财/新浪/AkShare）提供 L1 快照；Level-2 提供十档盘口、逐笔成交、
委托队列等高频数据，通常由券商 SDK / 行情厂商（如通达信、恒生、聚源、Wind）提供。

本文件定义统一抽象 ``Level2Source`` 与占位实现 ``BrokerLevel2Stub``。接入真实券商时，
继承 ``Level2Source`` 实现 ``fetch_order_book_10`` / ``fetch_ticks`` 即可，无需改动上层服务。
（注：平台已内置 tdx-connector / gildata 等 MCP 连接器，可在该层桥接。）
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Optional

from .base import QuoteSource

logger = logging.getLogger(__name__)


@dataclass
class OrderBook10:
    """十档盘口。"""

    code: str
    bids: list[tuple[float, int]] = field(default_factory=list)   # [(价, 量), ...] 买一..买十
    asks: list[tuple[float, int]] = field(default_factory=list)   # [(价, 量), ...] 卖一..卖十
    ts: float = 0.0


class Level2Source(abc.ABC):
    """Level-2 数据源抽象。"""

    name: str = "level2"

    @abc.abstractmethod
    async def fetch_order_book_10(self, code: str) -> OrderBook10:
        """取十档盘口。"""

    @abc.abstractmethod
    async def fetch_ticks(self, code: str, limit: int = 100) -> list[dict]:
        """取最近逐笔成交。"""


class BrokerLevel2Stub(Level2Source):
    """占位实现：演示如何桥接券商 SDK，未配置时抛 NotImplemented。

    接入示例：
        class MyBrokerLevel2(Level2Source):
            async def fetch_order_book_10(self, code):
                # 调用券商 SDK / 行情网关 WebSocket
                ...
    """

    name = "broker_level2_stub"

    async def fetch_order_book_10(self, code: str) -> OrderBook10:  # pragma: no cover
        raise NotImplementedError(
            "Broker Level-2 未配置。请继承 Level2Source 实现 fetch_order_book_10 / "
            "fetch_ticks，并通过 settings 注入实例。"
        )

    async def fetch_ticks(self, code: str, limit: int = 100) -> list[dict]:  # pragma: no cover
        raise NotImplementedError("Broker Level-2 未配置。")


# 全局 Level-2 实例（默认占位；运行时可被替换为真实券商实现）
level2: Level2Source = BrokerLevel2Stub()
