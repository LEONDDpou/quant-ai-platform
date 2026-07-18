# 部署方法（市场实时模块）

模块复用既有 `quant-ai-platform` 的全栈编排，仅需少量增量配置。

## 1. 环境变量（后端）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `MARKET_DB_URL` | 市场模块独立异步数据库连接串 | `sqlite+aiosqlite:///./market.db` |
| `MARKET_REFRESH_RATE` | 实时刷新间隔（秒，1/3/5） | `3` |
| `MARKET_SOURCE_ORDER` | 数据源优先级 | `tencent,eastmoney,sina,akshare` |
| `MARKET_SOURCE_TIMEOUT` | 单源超时（秒） | `8.0` |
| `MARKET_SOURCE_RETRIES` | 单源重试次数 | `2` |
| `MARKET_CB_FAIL_THRESHOLD` | 熔断器失败阈值 | `5` |
| `MARKET_CB_COOLDOWN` | 熔断冷却（秒） | `30.0` |
| `MARKET_RATE_LIMIT_PER_SEC` | 全局令牌桶限流（次/秒） | `10` |
| `MARKET_TRUST_ENV` | 是否信任系统代理（沙箱建议 false） | `false` |
| `MARKET_DEFAULT_WATCHLIST` | WS 默认关注池 | `sh000001,sz399001,sh000300,600519,sz000858,600036` |

> 生产 PostgreSQL 示例：`MARKET_DB_URL=postgresql+asyncpg://quant:quant123@postgres:5432/quantdb`

## 2. 依赖

`requirements.txt` 已新增异步驱动：
```
aiosqlite==0.20.0     # 本地 SQLite 异步
asyncpg==0.30.0       # 生产 PostgreSQL 异步
```
Docker 镜像通过 `pip install -r requirements.txt` 自动安装，无需额外步骤。

## 3. Docker Compose（全栈编排）

`docker-compose.yml` 的 `backend` 服务已增加：
```yaml
environment:
  DATABASE_URL: postgresql+psycopg://quant:quant123@postgres:5432/quantdb
  MARKET_DB_URL: postgresql+asyncpg://quant:quant123@postgres:5432/quantdb   # 新增
  WESTOCK_SCRIPT: /app/westock/index.js
  NODE_BIN: /usr/bin/node
  ...
```
`nginx` 已统一把 `/api`、`/ws` 反向代理到后端，前端 `NEXT_PUBLIC_API_BASE` 在构建期设为 `""`（走相对路径）。

## 4. 启动步骤

```bash
# 方式 A：Docker（推荐生产）
cp .env.example .env          # 填入 LLM_API_KEY 等
docker compose up -d --build  # 构建并启动 postgres / backend / frontend / nginx
# 访问 http://<服务器IP>  →  侧边栏「市场监控 / 实时行情」

# 方式 B：本地分离开发
# 终端 1 — 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning
# 终端 2 — 前端
cd frontend
npm install && npm run dev      # 默认 http://localhost:3000
```

## 5. 健康检查与验证

```bash
# 后端 API 是否正常
curl http://localhost:8000/api/market/sources
curl "http://localhost:8000/api/market/realtime?codes=600519,000858"

# 启动日志中应出现
# [market_ws] 实时推送循环启动，关注池 N 只，刷新间隔 3s
```

## 6. 注意事项

- **WebSocket 同源**：前端开发态（:3000）连接后端（:8000）的 `/ws/market/realtime`，后端已对 `localhost:3000` 来源放行；生产经 nginx 同域无此问题。
- **K 线/资金流依赖 westock Node 脚本**：需 Node ≥ 18，`WESTOCK_SCRIPT` / `NODE_BIN` 已配置。
- **实时推送单例**：`market_realtime_feed_loop` 仅在 `app.main` 的 lifespan 中以单任务启动，确保关注池仅被批量拉取一次、多个 WS 客户端共享。
- **AI 评分为模型驱动**：展示与接口均标注「非投资建议、非交易信号」。
