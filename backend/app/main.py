"""AI A股量化智能交易平台 - FastAPI 主应用"""
import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.routers import dashboard, market, strategy, news, backtest, stock, ai_researcher, chat, abu_ml, factor, stock_picker, market_dynamics, stock_detail, market_temperature, ai_agent, alerts, multi_factor, portfolio, institution
from app.paper.routers import account as paper_account_router
from app.paper.routers import market as paper_market_router
from app.paper.routers import order as paper_order_router
from app.paper.routers import position as paper_position_router
from app.paper.routers import risk as paper_risk_router
from app.paper.routers import stats as paper_stats_router
from app.paper.routers import auto_trade as paper_auto_router
from app.paper.routers import backtest as paper_backtest_router
from app.paper.routers import pool as paper_pool_router
from app.paper.routers import research as paper_research_router
from app.paper.routers import strategy_marketplace as paper_marketplace_router
from app.paper.routers import portfolio as paper_portfolio_router
from app.paper.routers import daily_review as paper_daily_review_router
from app.paper.ws_feed import paper_market_feed_loop, WATCHLIST
from app.paper.services import tencent_quote
from app.paper.services.auto_trade_service import AutoTradeService
from app.paper.repositories.account_repo import AccountRepository
from app.paper.risk_monitor import risk_monitor_loop
from app.paper.pool_monitor import pool_maintenance_loop
from app.paper.research_monitor import researcher_loop
from app.paper.daily_review_monitor import daily_review_loop
from app.paper.unified_analysis_loop import unified_analysis_loop
from app.paper.services.order_service import OrderService as _PaperOrderService
# ===== 实时行情 / 市场动态新模块（多源故障切换 + WebSocket 推送）=====
from app.market.routers import market as market_rt_router
from app.market.ws.feed import register_market_ws, market_realtime_feed_loop
from app.services import data_provider as dp
from app.db.database import init_db
from app.ws.manager import ConnectionManager, SUB_ALL
from app.ws.feed import market_feed_loop

# 允许的前端跨域来源（WebSocket 握手时校验 Origin）
ALLOWED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
}

logger = logging.getLogger(__name__)


async def _warmup_tencent_quotes(codes: list) -> None:
    """应用启动时预热腾讯实时行情缓存（非阻塞后台任务，失败仅告警）。

    启动即后台拉取一次关注池行情，使首个 WS 推送 / REST 请求即可拿到真实数据。
    之后由 WS 推送循环按订阅关系周期刷新共享缓存，全平台仅此一处发起批量拉取。
    ``tencent_quote.fetch_quotes`` 为同步 requests 调用（走代理、不触碰事件循环），
    用 ``asyncio.to_thread`` 执行，无 uvloop 冲突风险。
    """
    try:
        await asyncio.to_thread(tencent_quote.fetch_quotes, list(codes))
        logger.info("[Startup] 腾讯行情缓存预热完成（%d 只）", len(codes))
    except Exception as e:  # noqa: BLE001
        logger.warning("[Startup] 腾讯行情预热失败（可忽略，推送循环会自动重试）: %s", e)


async def _warmup_caches():
    """应用启动时预热 dashboard 聚合缓存，避免首个用户请求触发 9 路并发
    westock/LLM shell-out 导致首屏数秒卡顿。非阻塞后台任务，失败仅告警。"""
    try:
        from app.routers.dashboard import get_dashboard_v2
        await asyncio.to_thread(get_dashboard_v2)
        logger.info("[Startup] dashboard_v2 缓存预热完成")
    except Exception as e:
        logger.warning("[Startup] dashboard_v2 缓存预热失败（可忽略，首次请求会自动重建）: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] AI A股量化智能交易平台 后端服务启动")
    # 1) 初始化数据库（建表，幂等）
    init_db()
    # 1.1) 初始化市场模块异步库（PostgreSQL / SQLite，建表幂等）
    try:
        from app.market.core.db import init_models

        await init_models()
    except Exception as e:  # noqa: BLE001
        logger.warning("[Startup] 市场模块库初始化失败（延迟到首次写入）: %s", e)
    # 2) 启动 WebSocket 实时行情推送循环
    # 各 WS 端点使用独立的连接管理器，避免广播跨端点串扰
    # （原单一 manager 导致 /ws/market 的 broadcast 误发给 /ws/paper/market 订阅方）
    app.state.ws_market = ConnectionManager()
    app.state.ws_paper = ConnectionManager()
    app.state.ws_alerts = ConnectionManager()
    app.state.ws_dashboard = ConnectionManager()
    feed_task = asyncio.create_task(market_feed_loop(app))
    # 2.x) 注册实时行情 WebSocket 端点 + 第 5 个独立连接管理器
    register_market_ws(app)
    # 2.1) 启动模拟盘实时行情推送循环（M2）
    paper_feed_task = asyncio.create_task(paper_market_feed_loop(app))
    # 2.1.1) 预热腾讯实时行情缓存：启动即后台拉取一次关注池行情，
    #        使首个 WS 推送 / REST 请求即可拿到真实数据（非阻塞，失败仅告警）。
    #        之后由 WS 推送循环按订阅关系周期刷新共享缓存，全平台仅此一处拉取。
    snapshot_task = asyncio.create_task(_warmup_tencent_quotes(WATCHLIST))
    # 2.2) 启动模拟盘挂单重试撮合循环（M3）：每 5s 按行情撮合 pending 订单
    paper_match_task = asyncio.create_task(_paper_order_match_loop())
    # 2.3) 启动 AI 自动交易后台循环（M7）：每 ~30s 对启用策略的账户跑一轮
    paper_ai_task = asyncio.create_task(_paper_ai_loop())
    # 2.4) 启动智能风控自动监控循环（智能风控中心）：每 60s 扫描全账户风险与自定义规则
    paper_risk_monitor_task = asyncio.create_task(risk_monitor_loop(60.0))
    # 2.5) 启动股票池自动维护循环（M179）：每 300s 同步成分 + 健康检测 + 自动移除
    paper_pool_task = asyncio.create_task(pool_maintenance_loop(300.0))
    # 2.6) 启动研究员 Agent 自动研究循环（#182）：每 3600s 对默认宇宙跑规则确定性研究
    paper_research_task = asyncio.create_task(unified_analysis_loop(3600.0))
    paper_daily_review_task = asyncio.create_task(daily_review_loop(3600.0))
    # 2.7) 启动模拟盘日终滚动调度（T+1）：每日收盘后自动解锁当日买入
    paper_rollover_task = asyncio.create_task(_paper_daily_rollover_loop())
    # 2.8) 预热 dashboard 聚合缓存（避免首个请求冷启动卡顿，非阻塞）
    asyncio.create_task(_warmup_caches())
    # 2.9) 启动实时行情 WebSocket 推送循环（新模块）
    market_rt_task = asyncio.create_task(market_realtime_feed_loop(app))
    yield
    # 3) 关闭时取消推送循环（snapshot_task 为 asyncio 预热任务，yield 后取消）
    feed_task.cancel()
    paper_feed_task.cancel()
    paper_match_task.cancel()
    paper_ai_task.cancel()
    paper_risk_monitor_task.cancel()
    paper_pool_task.cancel()
    paper_research_task.cancel()
    paper_daily_review_task.cancel()
    paper_rollover_task.cancel()
    market_rt_task.cancel()
    for t in (feed_task, paper_feed_task, paper_match_task, paper_ai_task, paper_risk_monitor_task, paper_pool_task, paper_research_task, paper_daily_review_task, paper_rollover_task, market_rt_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    print("[Shutdown] 后端服务关闭")


app = FastAPI(
    title="AI A股量化智能交易平台 API",
    description="面向中国A股市场的AI量化交易系统",
    version="1.3.3",
    lifespan=lifespan,
)

# CORS - 允许前端跨域访问
# 生产环境通过环境变量 CORS_ALLOW_ORIGINS 指定可信前端域名（逗号分隔，如
#   "https://app.example.com,https://www.example.com"）；
# 未设置时默认放行任意来源（开发态便利，且不携带凭据）。
_cors_env = os.environ.get("CORS_ALLOW_ORIGINS", "*")
if _cors_env.strip() == "*":
    _allowed_origins = ["*"]
else:
    _allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(strategy.router, prefix="/api/strategies", tags=["Strategy"])
app.include_router(news.router, prefix="/api/news", tags=["News"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(stock.router, prefix="/api/stock", tags=["Stock"])
app.include_router(ai_researcher.router, prefix="/api/ai-researcher", tags=["AIResearcher"])
app.include_router(chat.router, prefix="/api/ai", tags=["AIChat"])
app.include_router(abu_ml.router, prefix="/api/abu-ml", tags=["AbuML"])
app.include_router(factor.router, prefix="/api/factor", tags=["Factor"])
app.include_router(stock_picker.router, prefix="/api/stock-picker", tags=["StockPicker"])
app.include_router(market_dynamics.router, prefix="/api/market-dynamics", tags=["MarketDynamics"])
app.include_router(stock_detail.router, prefix="/api/stock-detail", tags=["StockDetail"])
# v1.0 新增路由
app.include_router(market_temperature.router, prefix="/api/market-temperature", tags=["MarketTemperature"])
app.include_router(ai_agent.router, prefix="/api/ai-agent", tags=["AIAgent"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(multi_factor.router, prefix="/api/multi-factor", tags=["MultiFactor"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])
# v1.3 新增路由
app.include_router(institution.router, prefix="/api/institution", tags=["Institution"])
# ===== 实时行情 / 市场动态（新模块：多源故障切换 + WebSocket 推送）=====
app.include_router(market_rt_router.router, prefix="/api/market", tags=["MarketRealtime"])
# ===== 模拟盘交易系统（Paper Trading）=====
app.include_router(paper_account_router.router, prefix="/api/paper/account", tags=["PaperAccount"])
app.include_router(paper_market_router.router, prefix="/api/paper/market", tags=["PaperMarket"])
app.include_router(paper_order_router.router, prefix="/api/paper/order", tags=["PaperOrder"])
app.include_router(paper_position_router.router, prefix="/api/paper/position", tags=["PaperPosition"])
app.include_router(paper_risk_router.router, prefix="/api/paper/risk", tags=["PaperRisk"])
app.include_router(paper_stats_router.router, prefix="/api/paper/stats", tags=["PaperStats"])
app.include_router(paper_auto_router.router, prefix="/api/paper/auto", tags=["PaperAuto"])
app.include_router(paper_backtest_router.router, prefix="/api/paper/backtest", tags=["PaperBacktest"])
app.include_router(paper_pool_router.router, prefix="/api/paper/pool", tags=["PaperPool"])
app.include_router(paper_research_router.router, prefix="/api/paper/research", tags=["PaperResearch"])
app.include_router(paper_marketplace_router.router, prefix="/api/paper/strategy-marketplace", tags=["PaperMarketplace"])
app.include_router(paper_portfolio_router.router, prefix="/api/paper/portfolio", tags=["PaperPortfolio"])
app.include_router(paper_daily_review_router.router, prefix="/api/paper/daily-review", tags=["PaperDailyReview"])


# ==================== 模拟盘挂单重试撮合后台循环（M3） ====================
async def _paper_order_match_loop(interval: float = 5.0):
    """每 interval 秒对全部 pending/partial 订单按最新行情重试撮合。"""
    import asyncio as _asyncio
    svc = _PaperOrderService()
    while True:
        try:
            await _asyncio.to_thread(svc.retry_pending_orders)
        except Exception as e:
            logger.warning("[paper_match_loop] 撮合异常: %s", e)
        await _asyncio.sleep(interval)


# ==================== AI 自动交易后台循环（M7） ====================
async def _paper_ai_loop(interval: float = 30.0):
    """每 interval 秒扫描所有模拟账户，对其启用策略跑一轮 AI 自动交易。"""
    import asyncio as _asyncio
    svc = AutoTradeService()
    acct_repo = AccountRepository()
    while True:
        try:
            accounts = acct_repo.list_accounts()
            for acct in accounts:
                try:
                    if svc.strategy_repo.enabled_for_account(acct.id):
                        await _asyncio.to_thread(svc.run_once, acct.id)
                except Exception as e:
                    logger.warning("[paper_ai_loop] 账户 %s 执行异常: %s", acct.id, e)
        except Exception as e:
            logger.warning("[paper_ai_loop] 循环异常: %s", e)
        await _asyncio.sleep(interval)


# ==================== 模拟盘日终滚动调度（T+1 解锁） ====================
async def _paper_daily_rollover_loop():
    """每日收盘后（15:10）自动对全账户执行 T+1 日终滚动：
    当日买入股份转为可卖、持仓天数 +1。"""
    from app.paper.services.position_service import PositionService
    last_rolled = None
    while True:
        await asyncio.sleep(60)
        try:
            now = datetime.now()
            today = now.date()
            if now.hour > 15 or (now.hour == 15 and now.minute >= 10):
                if last_rolled != today:
                    svc = PositionService()
                    for acct in AccountRepository().list_accounts():
                        try:
                            svc.rollover_day(acct.id)
                        except Exception as e:
                            logger.warning("[rollover] 账户 %s 失败: %s", acct.id, e)
                    last_rolled = today
                    logger.info("[rollover] 日终滚动完成 %s", today)
        except Exception as e:
            logger.warning("[rollover] 调度异常: %s", e)


# ==================== WebSocket 实时行情推送 ====================
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    """WebSocket 实时行情推送（真实 westock 数据，由后台循环广播）。"""
    origin = ws.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        await ws.close(code=4403)
        return

    manager = app.state.ws_market
    await manager.connect(ws)

    # 连接即推送一帧即时快照，避免客户端等待首个推送周期
    try:
        from app.ws.feed import fetch_indices_payload
        snapshot = {
            "type": "snapshot",
            "ts": __import__("datetime").datetime.now().isoformat(),
            "indices": fetch_indices_payload(),
            "stocks": [],
        }
        await ws.send_json(snapshot)
    except Exception:
        pass

    try:
        # 保持连接；客户端发来任意消息即忽略，断开时抛 WebSocketDisconnect
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ==================== WebSocket 模拟盘实时行情推送（M2） ====================
@app.websocket("/ws/paper/market")
async def ws_paper_market(ws: WebSocket):
    """模拟盘实时行情推送（关注池行情 + 五档，由后台循环按订阅定向推送）。

    客户端协议（JSON 文本帧）：
      {"action":"subscribe","codes":["600519","000858"]}   订阅指定标的
      {"action":"subscribe","channel":"all"}               订阅全部（共享快照内全部代码）
      {"action":"unsubscribe","codes":[...]}              取消订阅
      {"action":"unsubscribe","channel":"all"}             取消全部订阅
      {"action":"ping"}                                   心跳，服务端回 {"type":"pong"}
    未发送任何订阅消息的连接，默认接收 WATCHLIST（保持历史行为）。
    """
    origin = ws.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        await ws.close(code=4403)
        return

    manager = app.state.ws_paper
    await manager.connect(ws)
    # 不预先订阅：未发 subscribe 的连接在 init_done 后由 publish_market 默认推送
    # WATCHLIST；已发 subscribe 的连接严格按订阅过滤（避免「自动订阅全量」覆盖
    # 显式单标的订阅）。

    # 先处理客户端首条消息（通常是 subscribe / ping），以便即时快照按订阅过滤，
    # 且避免「未订阅就被先灌一帧整表快照」。超时（无首条消息）则按默认行为处理。
    _initial = None
    try:
        _initial = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        _initial = None

    if _initial:
        try:
            _msg = json.loads(_initial)
            _action = _msg.get("action")
            if _action in ("subscribe", "unsubscribe"):
                if _msg.get("channel") == "all":
                    _codes = [SUB_ALL]
                else:
                    _codes = [str(c) for c in (_msg.get("codes") or [])]
                if _action == "subscribe":
                    manager.subscribe(ws, _codes)
                else:
                    manager.unsubscribe(ws, _codes)
            elif _action == "ping":
                await ws.send_json({"type": "pong", "ts": datetime.now().isoformat(timespec="seconds")})
        except Exception:
            pass

    # 首条消息处理完毕，标记连接可参与正常推送（解除 _pending 保护）
    manager.init_done(ws)

    # 连接即推送一帧即时快照（按当前订阅过滤），避免客户端等待首个推送周期
    try:
        from app.paper.ws_feed import build_quotes
        quotes = build_quotes()
        subs = manager._subs.get(ws, set())
        if not subs:
            want = set(WATCHLIST)
        elif SUB_ALL in subs:
            want = set(quotes.keys())
        else:
            want = subs
        await ws.send_json({
            "type": "paper_market_tick",
            "ts": datetime.now().isoformat(timespec="seconds"),
            "quotes": [quotes[c] for c in want if c in quotes],
        })
    except Exception:
        pass

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            action = msg.get("action")
            if action in ("subscribe", "unsubscribe"):
                if msg.get("channel") == "all":
                    codes = [SUB_ALL]
                else:
                    codes = [str(c) for c in (msg.get("codes") or [])]
                if action == "subscribe":
                    manager.subscribe(ws, codes)
                else:
                    manager.unsubscribe(ws, codes)
            elif action == "ping":
                await ws.send_json({"type": "pong", "ts": datetime.now().isoformat(timespec="seconds")})
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ==================== WebSocket 预警推送 ====================
@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    """WebSocket 预警实时推送。"""
    origin = ws.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        await ws.close(code=4403)
        return

    manager = app.state.ws_alerts
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ==================== WebSocket Dashboard V2 推送 ====================
@app.websocket("/ws/dashboard")
async def ws_dashboard_v2(ws: WebSocket):
    """WebSocket Dashboard V2 六屏数据推送（10s 间隔）。"""
    origin = ws.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        await ws.close(code=4403)
        return

    manager = app.state.ws_dashboard
    await manager.connect(ws)

    import asyncio as _asyncio
    try:
        while True:
            try:
                from app.routers.dashboard import get_dashboard_v2
                # FastAPI route 函数是同步的，在 WS 循环中用 loop.run_in_executor 避免阻塞
                loop = _asyncio.get_running_loop()
                payload = await loop.run_in_executor(None, get_dashboard_v2)
                await ws.send_json({"type": "dashboard_v2", "ts": __import__("datetime").datetime.now().isoformat(), "data": payload})
            except Exception:
                pass
            # 同时接收客户端消息（ping 等），超时后继续循环
            try:
                await _asyncio.wait_for(ws.receive_text(), timeout=10)
            except _asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


# ==================== Health Check & Metrics ====================
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "AI Quant Platform API",
        "version": "1.0.0",
        "db": "postgresql" if "postgresql" in os.environ.get("DATABASE_URL", "") else "sqlite",
    }


@app.get("/metrics")
def metrics():
    """Prometheus 指标暴露端点。"""
    from prometheus_client import generate_latest, REGISTRY
    return Response(
        content=generate_latest(REGISTRY).decode("utf-8"),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/")
def root():
    return {
        "name": "AI A股量化智能交易平台 API",
        "version": "1.3.3",
    }
