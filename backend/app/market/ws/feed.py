"""市场实时行情 WebSocket 推送（需求 7）。

行情服务器 → WebSocket → 前端 Dashboard，实现股票价格实时刷新。
  * 后台循环按 settings.refresh_rate（1/3/5s 可配置）批量刷新关注池行情；
  * 通过第 5 个独立 ConnectionManager 广播，避免与其他 WS 端点串扰；
  * 每帧推送后异步落库（best-effort），并对断线连接自动由前端重连；
  * 全部源不可用时保留上一次成功快照（serve-stale），前端不空屏。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from ..core.config import settings
from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

# 第 5 个独立连接管理器（与现有 4 个端点隔离）
manager = ConnectionManager()
_loop_task: asyncio.Task | None = None


async def market_realtime_feed_loop(app) -> None:  # noqa: ANN001
    from ..services import quote_service
    from ..services.persistence import save_breadth, save_quotes
    from ..services.market_monitor import get_breadth

    codes = settings.watchlist
    logger.info("[market_ws] 实时推送循环启动，关注池 %d 只，刷新间隔 %ds", len(codes), settings.refresh_rate)
    tick = 0
    while True:
        try:
            quotes = await quote_service.refresh(codes)
            if quotes:
                payload = {
                    "type": "market_realtime",
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": quote_service.orchestrator.last_source,
                    "quotes": [q.to_dict() for q in quotes.values()],
                }
                await manager.broadcast(payload)
                # 异步落库（不阻塞推送）
                asyncio.create_task(save_quotes(list(quotes.values())))
                # 每 ~10 个周期持久化一次市场宽度
                if tick % 10 == 0:
                    try:
                        breadth = await get_breadth()
                        asyncio.create_task(save_breadth(breadth))
                    except Exception as e:  # noqa: BLE001
                        logger.warning("[market_ws] 宽度持久化失败: %s", e)
            else:
                logger.warning("[market_ws] 本周期未获取到任何行情（全部源不可用）")
        except Exception as e:  # noqa: BLE001
            logger.warning("[market_ws] 推送循环异常: %s", e)
        tick += 1
        await asyncio.sleep(settings.refresh_rate)


def register_market_ws(app) -> None:  # noqa: ANN001
    """在 lifespan 中调用：注册 WS 端点并创建连接管理器。"""
    app.state.ws_market_rt = manager

    @app.websocket("/ws/market/realtime")
    async def ws_market_realtime(ws: WebSocket):
        origin = ws.headers.get("origin", "")
        allowed = {"http://localhost:3000", "http://127.0.0.1:3000"}
        if origin and origin not in allowed:
            await ws.close(code=4403)
            return
        await manager.connect(ws)
        # 连接即推一帧当前快照
        try:
            from ..services import quote_service

            snap = await quote_service.get_snapshot()
            if snap:
                await ws.send_json({
                    "type": "market_realtime",
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": quote_service.orchestrator.last_source,
                    "quotes": [q.to_dict() for q in snap.values()],
                })
        except Exception:  # noqa: BLE001
            pass
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(ws)
