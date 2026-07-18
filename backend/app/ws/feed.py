"""WebSocket 实时行情推送循环。

机制：后台 asyncio 任务，每隔 PUSH_INTERVAL 秒拉取一次真实行情
（westock-data → data_provider），构造 payload 后：
  1) 落库 market_snapshots（时间序列，供回放/审计）
  2) 广播给所有已连接的 WebSocket 客户端

说明：A股无免费交易所直连 tick 源，这里用「真实日/快照行情 + 定时轮询」
实现秒级刷新，是真实可行的「准实时」方案；若后续接入level-2或券商
实时网关，只需替换 fetch_market_payload 的数据源即可。
"""
import asyncio
import datetime
import os

from app.services import data_provider as dp
from app.db import crud

# 关注池（与 LLM 报告一致）
WATCHLIST = ["600519", "300750", "601318", "000858", "600036"]

PUSH_INTERVAL = int(os.environ.get("WS_PUSH_INTERVAL", "5"))   # 秒
STOCK_EVERY = int(os.environ.get("WS_STOCK_EVERY", "6"))        # 每 N 次推送带一次个股


def fetch_indices_payload() -> list[dict]:
    """拉取 5 大指数真实行情（与 dashboard 同源）。"""
    return dp.get_indices()


def fetch_stocks_payload() -> list[dict]:
    """拉取关注池个股实时快照。"""
    out = []
    for code in WATCHLIST:
        try:
            a = dp.get_stock_analysis(code)
            out.append({
                "code": a["code"],
                "name": a["name"],
                "price": a["currentPrice"],
                "changePct": a["changePct"],
                "aiScore": a["aiScore"],
            })
        except Exception:
            continue
    return out


def build_payload(include_stocks: bool) -> dict:
    indices = fetch_indices_payload()
    payload = {
        "type": "snapshot" if not include_stocks else "tick",
        "ts": datetime.datetime.now().isoformat(),
        "indices": indices,
        "stocks": fetch_stocks_payload() if include_stocks else [],
    }
    return payload


async def market_feed_loop(app) -> None:
    """常驻推送循环；异常自愈，不退出。"""
    manager = app.state.ws_market
    tick = 0
    print(f"[WS feed] started, interval={PUSH_INTERVAL}s, watchlist={len(WATCHLIST)}")
    while True:
        try:
            tick += 1
            include_stocks = (tick % STOCK_EVERY == 0)
            # 阻塞调用放到线程，避免卡住事件循环
            payload = await asyncio.to_thread(build_payload, include_stocks)
            # 落库（时间序列）
            snap = dict(payload)
            await asyncio.to_thread(crud.save_snapshot, snap)
            # 广播
            await manager.broadcast(payload)
            if tick % STOCK_EVERY == 0:
                print(f"[WS feed] tick#{tick} broadcasted indices+stocks, clients={manager.count()}")
        except Exception as e:  # noqa: BLE001
            print(f"[WS feed] error: {type(e).__name__}: {e}")
        await asyncio.sleep(PUSH_INTERVAL)
