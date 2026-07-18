# AI A股量化智能交易平台

> 面向中国A股市场的AI量化交易系统 — 策略回测、智能选股、自动交易

## 技术栈

### 前端
- **Next.js 16** + TypeScript
- **Tailwind CSS** — 深色金融科技UI风格
- **ECharts** — 专业金融图表
- **lucide-react** — 图标库
- **Zustand** — 状态管理

### 后端
- **Python FastAPI** — 高性能异步API框架
- **SQLAlchemy 2.0** — ORM 持久层（PostgreSQL 生产 / SQLite 验证，同一套代码）
- **WebSocket** — 实时行情推送（westock 真实数据，秒级刷新）
- **Pydantic** — 数据校验
- **Redis** — 缓存（规划中）
- **Celery** — 任务调度（规划中）

### AI 模型
- **大语言模型 AI 量化研究员 Agent** — OpenAI 兼容接口（DeepSeek / 通义千问 / OpenAI 等），详见 backend/.env.example

## 项目结构

```
quant-ai-platform/
├── frontend/              # Next.js 前端
│   ├── src/
│   │   ├── app/           # 页面路由
│   │   │   ├── dashboard/         # 交易驾驶舱
│   │   │   ├── strategies/        # AI量化策略中心
│   │   │   ├── ai-researcher/     # AI量化研究员
│   │   │   ├── stock-analysis/    # 股票智能分析
│   │   │   ├── news/              # 新闻与市场情绪
│   │   │   ├── backtest/          # 回测系统
│   │   │   └── trading/           # 自动交易系统
│   │   ├── components/    # 组件
│   │   │   ├── layout/            # 布局组件（Sidebar, TopBar）
│   │   │   ├── charts/            # 图表组件（ECharts）
│   │   │   ├── cards/             # 卡片组件
│   │   │   └── ui/                # UI 组件
│   │   ├── lib/           # 工具库
│   │   ├── types/         # TypeScript 类型定义
│   │   └── hooks/         # React Hooks
│   ├── tailwind.config.ts # Tailwind 配置（深色金融科技主题）
│   └── package.json
├── backend/               # FastAPI 后端
│   ├── app/
│   │   ├── main.py        # FastAPI 主应用
│   │   ├── routers/       # API 路由
│   │   │   ├── dashboard.py       # 交易驾驶舱 API
│   │   │   ├── market.py          # 市场行情 API
│   │   │   ├── strategy.py        # 策略管理 API
│   │   │   ├── news.py            # 新闻情绪 API
│   │   │   ├── backtest.py        # 回测系统 API
│   │   │   ├── trading.py         # 交易系统 API
│   │   │   ├── stock.py           # 个股分析 API
│   │   │   └── ai_researcher.py   # AI 研究员 (LLM) API
│   │   ├── models/        # 数据模型
│   │   ├── db/            # 持久层（SQLAlchemy）
│   │   │   ├── database.py     # 引擎/Session/建表
│   │   │   ├── models.py       # ORM 模型
│   │   │   └── crud.py         # 读写操作
│   │   ├── ws/            # WebSocket 实时推送
│   │   │   ├── manager.py       # 连接管理/广播
│   │   │   └── feed.py          # 行情推送循环
│   │   └── services/      # 服务层
│   │       ├── westock_client.py  # 腾讯自选股真实行情客户端
│   │       ├── data_provider.py   # 真实数据层 + 指标计算
│   │       ├── backtest_engine.py # 真实K线回测引擎
│   │       └── llm_service.py     # LLM 接入层 (OpenAI 兼容)
│   ├── requirements.txt
│   └── run.py             # 启动脚本
├── data/                  # 数据采集脚本
├── strategy/              # 策略代码
├── ai_agent/              # AI Agent 代码
├── backtest/              # 回测引擎
├── trading/               # 交易引擎
└── database/              # 数据库脚本
```

## 快速开始

### 前端

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
# 访问 http://localhost:3000
```

### 后端

```bash
cd backend
pip install -r requirements.txt
python run.py
# API 文档: http://localhost:8000/docs
```

## 功能模块

| 模块 | 路径 | 状态 | 说明 |
|------|------|------|------|
| 交易驾驶舱 | `/dashboard` | ✅ 真实数据 | 账户(合成)+ 指数(真实)+ 资金分析 + AI评分 |
| AI量化策略中心 | `/strategies` | ✅ MVP | 策略列表、创建新策略、回测/启停控制 |
| AI量化研究员 | `/ai-researcher` | ✅ LLM接入 | 每日投资报告(LLM/规则兜底)、个股深度解读 |
| 股票智能分析 | `/stock-analysis` | ✅ 真实数据 | 真实K线、技术指标、AI预测、多维评分 |
| 新闻与市场情绪 | `/news` | ✅ 真实数据 | 真实新闻列表、情绪指数、关联股票 |
| 回测系统 | `/backtest` | ✅ 真实数据 | 真实K线 MA交叉回测、收益曲线、交易记录 |
| 自动交易系统 | `/trading` | ✅ MVP | 下单、风控、委托记录 |
| 数据系统 | - | ✅ 接入中 | 腾讯自选股(westock) 真实行情，mock 兜底 |
| 实时行情推送 | `/dashboard` | ✅ 真时 | WebSocket 秒级推送真实指数/关注池，驾驶舱实时刷新 |
| 数据持久化 | - | ✅ 真时 | AI报告/回测/新闻/行情快照落库（PostgreSQL/SQLite） |
| AI策略生成器 | - | 🔜 规划中 | 自然语言生成策略代码 |

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/dashboard` | GET | 获取驾驶舱全量数据 |
| `/api/market/indices` | GET | 获取主要指数行情 |
| `/api/strategies` | GET/POST | 策略列表/创建策略 |
| `/api/strategies/{id}/toggle` | POST | 启动/停止策略 |
| `/api/news` | GET | 获取新闻列表 |
| `/api/news/ai-report` | GET | 获取AI研究报告 |
| `/api/stock/{code}/analysis` | GET | 个股全景分析(真实) |
| `/api/stock/{code}/kline` | GET | 个股K线(真实) |
| `/api/ai-researcher/report` | GET | AI研究员每日报告(LLM优先, 规则兜底) |
| `/api/ai-researcher/analyze?code=` | GET | 个股LLM深度解读 |
| `/api/backtest/run` | POST | 运行回测（结果落库） |
| `/api/backtest/history` | GET | 历史回测结果（持久化） |
| `/api/ai-researcher/history` | GET | 历史 AI 报告（持久化） |
| `/api/news/history` | GET | 历史新闻（持久化缓存） |
| `/api/trading/orders` | GET | 获取委托记录 |
| `/api/trading/order` | POST | 提交订单 |
| `/ws/market` | WS | WebSocket实时行情推送 |

## AI 研究员接入大模型（LLM）

AI 研究员（`/ai-researcher`）与个股解读（`/api/ai-researcher/analyze`）底层为
`app/services/llm_service.py`，采用 **OpenAI 兼容** 接口，因此 DeepSeek / 通义千问 /
文心一言 / OpenAI 均可直接接入，**无需改代码**，只需配置环境变量：

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入：
#   LLM_API_KEY=sk-xxx
#   LLM_BASE_URL=https://api.deepseek.com/v1   # 或通义/OpenAI 等
#   LLM_MODEL=deepseek-chat
python run.py
```

- 未配置 `LLM_API_KEY` 时，自动回退到规则合成，前端页面会明确标注「规则合成（未配置LLM）」；
  配置后切换为「大模型生成 · <model>」。
- 真实行情数据来自腾讯自选股（westock-data），调用失败时回退 mock，保证页面永远有内容。

## 开发路线图

### Phase 1 - MVP
- [x] 前端7大页面UI
- [x] FastAPI 后端API骨架
- [x] Mock数据驱动 → 已升级为「真实数据 + mock兜底」

### Phase 2 - 数据接入
- [x] 腾讯自选股(westock) 真实行情接入（指数/新闻/个股/K线）
- [x] **PostgreSQL / SQLite 持久化**（SQLAlchemy ORM：AI报告/回测/新闻/行情快照落库）
- [x] **WebSocket 真实行情推送**（westock 秒级轮询 + 广播，驾驶舱实时刷新）
- [ ] Redis 缓存 + Celery 任务调度

### Phase 3 - AI能力
- [x] LLM AI研究员 Agent（报告生成 + 个股解读，OpenAI 兼容）
- [ ] AI策略代码生成
- [ ] LSTM/Transformer 价格预测
- [ ] 新闻NLP情绪分析（当前为关键词启发式）

### Phase 4 - 交易系统
- [ ] 券商API实盘接入
- [ ] 自动化交易执行
- [ ] 高级风控引擎
- [ ] 组合管理

---

## PostgreSQL 持久化 + WebSocket 实时推送

### 持久化（落库对象）
- **AI 研究报告** `ai_reports`：每日报告（LLM/规则），含情绪分、关注股
- **回测结果** `backtest_results`：真实K线回测绩效（收益/夏普/回撤/交易）
- **新闻** `news_items`：去重缓存（`title|time` 唯一键）
- **行情快照** `market_snapshots`：WebSocket 推送逐帧落库（时间序列）
- **策略** `strategies`：策略中心元数据（预留）

ORM 用 SQLAlchemy 2.0，**同一套模型兼容 SQLite 与 PostgreSQL**，仅靠
`DATABASE_URL` 切换，无需改代码。

### 本地验证（SQLite，零依赖）
```bash
cd backend
cp .env.example .env
# 默认 DATABASE_URL=sqlite:///./quant.db 即可
python run.py
```

### 生产部署（PostgreSQL，一行切换）
```bash
# 1) 起库（需 Docker）
docker compose up -d postgres
# 2) 安装驱动
pip install "psycopg[binary]"
# 3) 改 backend/.env
DATABASE_URL=postgresql+psycopg://quant:quant123@localhost:5432/quantdb
python run.py
```

### 实时推送
- 后端启动即在后台跑 `market_feed_loop`：每 `WS_PUSH_INTERVAL`(默认5)秒拉取
  真实行情（5大指数 + 关注池个股），落库快照后通过 `/ws/market` 广播。
- 前端 `useMarketSocket` hook 订阅，驾驶舱指数卡与「实时关注」卡片秒级刷新，
  断线自动重连，并显示「实时推送 / LIVE」状态徽标。
- 说明：A股无免费交易所直连 tick 源，此处为「真实快照 + 定时轮询」的准实时方案；
  接入 level-2 / 券商实时网关时只需替换 `app/ws/feed.py` 的数据源。

## 开发原则

1. 先完成MVP，保证可运行
2. 每完成一个模块测试一次
3. 企业级代码规范
4. 增量迭代开发

---

⚠️ 本平台仅供学习研究使用，不构成任何投资建议。投资有风险，决策需谨慎。
