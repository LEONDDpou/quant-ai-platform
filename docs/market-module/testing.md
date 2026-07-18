# 测试方法（市场实时模块）

## 1. 后端单元测试

测试文件：`backend/tests/test_market_module.py`（离线、无网络依赖，可在 CI 直接运行）。

覆盖内容：
- **行情代码归一化** `normalize_code`（`sh600519` / `600519.SH` / `sz000858` 等形态）
- **K 线解析** `_parse_kline`（验证 westock 收盘列名为 `last`、open 缺失回退 close）
- **技术指标** `compute_technicals`（MA5/10/20、RSI14、MACD 字段完整性；短序列安全返回 None）
- **AI 量化评分** `compute_ai_score`（评分取值 [0,100]、风险等级映射、Pydantic `AIScoreOut` 校验）
- **可靠性原语** `CircuitBreaker`（CLOSED→OPEN→HALF_OPEN 状态机）、`RateLimiter`（令牌桶耗尽阻塞）、`retry`（指数退避重试 / 耗尽抛错）
- **多源故障切换** `FailoverOrchestrator`（首源失败自动降级到次源；全部失败抛 `SourceUnavailableError`；健康检查报告结构）
- **响应模型** `QuoteOut` / `BreadthOut` / `SourceHealth` 字段校验

### 运行方式

```bash
cd backend
# 方式 A：pytest（推荐，需安装 pytest）
python -m pytest tests/test_market_module.py -q

# 方式 B：unittest（无需额外依赖，项目 venv 默认可用）
python -m unittest discover -s tests -p "test_market_module.py"
```

> 测试在 `import` 前将 `DATABASE_URL` / `MARKET_DB_URL` 指向临时 SQLite，避免触碰主库。

## 2. 后端接口冒烟（手动）

服务启动后，对真实数据做端到端验证：

```bash
# 数据源健康（应 4 源可用、circuit=closed）
curl http://localhost:8000/api/market/sources

# AI 量化实时接口（含行情+资金流+技术+AI评分）
curl "http://localhost:8000/api/market/realtime?codes=600519,000858"

# 多周期 K 线
curl "http://localhost:8000/api/market/kline?code=600519&period=day&limit=60"

# 资金流（含北向 + 龙虎榜）
curl "http://localhost:8000/api/market/capital-flow?codes=600519"

# 市场监控（涨跌家数 / 排行 / 板块）
curl http://localhost:8000/api/market/monitor
```

预期：所有接口返回 200 且 `count` / `items` 非空；落库后 `market.db`（或 PostgreSQL）中
`market_realtime_quote` / `market_kline` / `market_ai_score` / `market_breadth` 出现新行。

## 3. WebSocket 推送验证（手动）

```bash
# 简易订阅（需 websocat 或浏览器 DevTools）
websocat ws://localhost:8000/ws/market/realtime
# 应周期性收到 {"type":"market_realtime","quotes":[...]}
```

## 4. 前端类型检查与构建

```bash
cd frontend
node_modules/.bin/tsc --noEmit     # 类型检查（应无报错）
npm run build                       # 生产构建，产出 .next/
npm run start                      # 启动生产服务（默认 :3000）
```

验证页面：侧边栏「市场监控 / 实时行情」→ 实时行情表、K 线图、资金流图、涨跌排行榜、AI 评分、风险预警均应正常渲染；
切换标的/周期即时刷新；WS 断开时出现「重连」按钮并保留上一次快照（serve-stale）。
