# 市场实时行情模块（app/market）— 总览与目录结构

> 为 AI 量化策略提供实时数据支撑的独立模块。后端 FastAPI + 独立异步数据层，前端 Next.js Dashboard，
> 多数据源故障切换，WebSocket 实时推送。商业级、模块化、可扩展至百万级标的。

## 功能覆盖（对应需求）

| 需求 | 能力 | 实现位置 |
| --- | --- | --- |
| 1 | 实时行情（价格/涨跌/量额/换手/PE/PB/市值，1/3/5s 可配） | `services/quote_service.py` + `ws/feed.py` |
| 2 | 多周期 K 线（分时/1m/5m/15m/30m/日/周/月，OHLCV+A） | `services/kline_service.py` |
| 3 | 资金流（主力/超大/大/中/小单 + 北向 + 龙虎榜） | `services/capital_flow_service.py` |
| 4 | 市场监控（涨跌停/涨跌家数/成交额/资金流/板块排名） | `services/market_monitor.py` |
| 5 | AI 量化接口 `/api/market/realtime`（行情+资金+技术+AI评分） | `routers/market.py` |
| 6 | 数据存储（PostgreSQL / SQLite） | `core/db.py` + `core/models.py` + `services/persistence.py` |
| 7 | WebSocket 实时推送 | `ws/feed.py` |
| 8 | 异常处理（故障切换 / 熔断 / 限流 / 重生 / 陈旧兜底） | `core/resilience.py` + `sources/failover.py` |
| 9 | 前端量化 Dashboard（行情表/K线/资金流/排行/AI评分/风险预警） | `frontend/src/app/market-realtime/page.tsx` |

## 目录结构

```
quant-ai-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI 入口：挂载 /api/market 路由 + /ws/market/realtime
│   │   └── market/                      # 新增市场实时模块（独立、可插拔，不复用主线 ORM）
│   │       ├── __init__.py
│   │       ├── schemas.py               # Pydantic 响应模型（QuoteOut/TechOut/CapitalFlowOut/AIScoreOut/...）
│   │       ├── routers/
│   │       │   └── market.py            # REST 路由 /api/market/*
│   │       ├── core/
│   │       │   ├── config.py            # MarketSettings（env 前缀 MARKET_）
│   │       │   ├── exceptions.py        # MarketError / SourceUnavailableError / ...
│   │       │   ├── resilience.py        # 重试（指数退避）/ 熔断器 / 令牌桶限流器
│   │       │   └── db.py                # 独立异步引擎 + Base（sqlite+aiosqlite / postgresql+asyncpg）
│   │       ├── sources/
│   │       │   ├── base.py              # Quote 归一化结构 + QuoteSource 接口 + normalize_code
│   │       │   ├── tencent.py           # 腾讯财经（首选源，HTTP 直连，绕过污染代理）
│   │       │   ├── eastmoney.py         # 东方财富（备用）
│   │       │   ├── sina.py              # 新浪财经（备用）
│   │       │   ├── akshare.py           # AkShare（兜底，懒加载，导入失败自动跳过）
│   │       │   ├── level2.py            # 券商 Level-2 扩展点（抽象基类 + 全局实例）
│   │       │   └── failover.py          # 多源故障切换编排器（优先级 + 熔断 + 限流 + 陈旧兜底）
│   │       ├── services/
│   │       │   ├── quote_service.py     # 实时行情服务（含异常/越界检测）
│   │       │   ├── technicals.py        # MA5/10/20、RSI14、MACD 技术指标
│   │       │   ├── ai_score.py          # AI 量化评分（透明启发式，非投资建议）
│   │       │   ├── kline_service.py     # 多周期 K 线（复用 westock Node CLI）
│   │       │   ├── capital_flow_service.py  # 资金流 / 北向 / 龙虎榜
│   │       │   ├── market_monitor.py    # 涨跌家数 / 排行榜 / 板块
│   │       │   └── persistence.py       # 落库（best-effort，异常吞掉不影响主链路）
│   │       └── ws/
│   │           └── feed.py              # WebSocket 实时推送 + 后台刷新循环（第 5 个独立 ConnectionManager）
│   ├── westock/                         # Node 单文件取数脚本（K线/资金流/龙虎榜/宽度）
│   └── tests/
│       └── test_market_module.py       # 单元 / 故障切换测试（离线、无网络依赖）
├── frontend/
│   └── src/
│       ├── lib/api.ts                   # 新增市场模块类型 + REST 函数（fetchMarket*）
│       ├── hooks/useMarketRealtimeSocket.ts  # 订阅 /ws/market/realtime 的 WS hook
│       ├── app/market-realtime/page.tsx # 实时行情 Dashboard 页面
│       └── components/layout/Sidebar.tsx     # 新增「实时行情」导航入口
├── docker-compose.yml                   # 后端新增 MARKET_DB_URL 指向 postgres(asyncpg)
└── requirements.txt                     # 新增 aiosqlite / asyncpg 异步驱动
```

## 设计要点

- **独立异步连接池**：`app/market` 使用独立的 `async_engine` 与 `Base`，与主线 SQLAlchemy 隔离，互不阻塞。
- **数据源可插拔**：所有源实现 `QuoteSource.fetch_quotes()`，编排器按 `source_order` 优先级故障切换。
- **可靠性原语**：每源独立熔断器 + 全局令牌桶限流 + 指数退避重试 + 陈旧数据兜底（serve-stale），保障前端不空屏。
- **真实数据源**：腾讯 `qt.gtimg.cn` 直连、东方财富 `push2`、新浪、AkShare；K线/资金流/龙虎榜复用已验证的 westock Node CLI。
- **AI 评分为模型驱动结果**：透明、可复现、可审计，明确标注「非投资建议、非交易信号」。

详见本目录其余文档：`api-design.md` / `database-design.md` / `deployment.md` / `testing.md`。
