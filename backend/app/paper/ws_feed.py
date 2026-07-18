"""模拟盘交易系统 — 实时行情 WebSocket 推送（M2）。

机制：后台 asyncio 任务，每隔 PUSH_INTERVAL 秒拉取关注池（watchlist）的
实时行情与五档盘口，构造 payload 后广播给所有连接到 /ws/paper/market 的客户端。

说明：
- 复用既有 app.ws.manager.ConnectionManager（与 /ws/market 同源管理器）；
- 行情来源走 MarketProvider（真实 akshare 优先，失败回退模拟），推送内容始终有数据；
- 推送的是「准实时」快照（真实源为日内轮询），若后续接入 Level-2 / 券商实时网关，
  只需替换 MarketProvider 的数据源，推送层无需改动。
"""
import asyncio
import datetime
import logging
import os

from app.paper.services.market_provider import market_provider
from app.paper.services.position_service import PositionService
from app.paper.repositories.account_repo import AccountRepository
from app.paper.services import tencent_quote

logger = logging.getLogger("paper.ws_feed")

# 关注池（可通过环境变量 PAPER_WATCHLIST 逗号分隔覆盖，如 600519,300750,000858）
_DEFAULT = "600519,300750,601318,000858,600036,002594,300750"
WATCHLIST = [c.strip() for c in os.environ.get("PAPER_WATCHLIST", _DEFAULT).split(",") if c.strip()]

PUSH_INTERVAL = int(os.environ.get("PAPER_WS_PUSH_INTERVAL", "5"))  # 秒
# 持仓市值刷新节流：每 N 次推送刷新一次全账户持仓市值（默认 6×5s=30s）。
# 避免每次推送都触发大量行情子进程调用（westock-data CLI）。
POSITION_REFRESH_EVERY = int(os.environ.get("PAPER_POSITION_REFRESH_EVERY", "6"))


def build_payload() -> dict:
    # 单次批量拉取关注池行情（共享缓存，全平台仅此一处发起网络请求），
    # 之后各 code 经 market_provider.quote 读缓存（命中真实源，失败回退模拟）。
    tencent_quote.fetch_quotes(WATCHLIST)
    quotes = []
    for code in WATCHLIST:
        try:
            q = market_provider.quote(code)
            quotes.append({
                "code": q["code"], "name": q["name"], "price": q["price"],
                "changePct": q["changePct"], "change": q["change"],
                "volume": q["volume"], "amount": q["amount"],
                "turnover": q["turnover"], "amplitude": q["amplitude"],
                "dataSource": q["dataSource"],
            })
        except Exception:
            continue
    return {
        "type": "paper_market_tick",
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "quotes": quotes,
    }


def build_quotes() -> dict:
    """返回 {code: quote_dict}。

    先批量拉取关注池（共享缓存，单网络请求），再逐码经 market_provider.quote
    读取（真实源优先，网络不可达时回退模拟）；推送循环按订阅关系过滤后定向下发。
    """
    tencent_quote.fetch_quotes(WATCHLIST)
    out: dict = {}
    for code in WATCHLIST:
        try:
            q = market_provider.quote(code)
            out[q["code"]] = q
        except Exception:
            continue
    return out


async def paper_market_feed_loop(app) -> None:
    """常驻推送循环；异常自愈，不退出。

    行情由腾讯实时接口（qt.gtimg.cn）按关注池批量拉取并写入共享缓存，
    本循环仅做读取 + 按订阅定向推送，**每个刷新周期仅一次批量网络请求**。

    并按 POSITION_REFRESH_EVERY 节流刷新全账户持仓市值，
    使 position.market_value 不再依赖手动调用刷新（P1-2 修复）。
    """
    manager = app.state.ws_paper
    pos_svc = PositionService()
    acct_repo = AccountRepository()
    print(f"[Paper WS feed] started, interval={PUSH_INTERVAL}s, watchlist={len(WATCHLIST)}")
    tick = 0
    while True:
        try:
            quotes = await asyncio.to_thread(build_quotes)
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            await manager.publish_market(quotes, ts, WATCHLIST)
            # 节流刷新持仓市值：每 POSITION_REFRESH_EVERY 次推送执行一次
            tick += 1
            if tick % POSITION_REFRESH_EVERY == 0:
                try:
                    accounts = acct_repo.list_accounts()
                    for acct in accounts:
                        try:
                            pos_svc.refresh_market_value_public(acct.id)
                        except Exception as e:  # 单账户失败不影响其他
                            logger.warning("[Paper WS feed] 刷新账户 %s 持仓市值失败: %s", acct.id, e)
                except Exception as e:
                    logger.warning("[Paper WS feed] 列举账户失败: %s", e)
        except Exception as e:  # noqa: BLE001
            print(f"[Paper WS feed] error: {type(e).__name__}: {e}")
        await asyncio.sleep(PUSH_INTERVAL)
