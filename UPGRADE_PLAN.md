# AI A股量化智能交易平台 → 机构级AI量化研究平台 升级方案

> 参考：幻方量化 · 九坤投资 · Two Sigma | 版本 v0.2.0 → v1.0.0

---

## 一、产品功能设计

### 1.1 核心定位升级

| 维度 | v0.2.0（当前） | v1.0.0（目标） |
|------|------------|-------------|
| 定位 | 个人量化工具 | 机构级AI量化研究平台 |
| 数据 | 部分真数据+大量Mock | 全链路真实数据驱动 |
| Dashboard | 单页交易驾驶舱 | 六屏专业终端布局 |
| AI能力 | 单一DeepSeek对话 | 多Agent协作（市场分析/因子研究/策略生成/监控预警） |
| 回测 | 单策略对比 | 策略矩阵+组合优化 |
| 风控 | 静态配置 | 实时动态风控+VaR/CVaR |

### 1.2 十大功能模块详解

#### 模块①：Dashboard信息架构优化
- 从单页面「交易驾驶舱」升级为**六屏矩阵**：
  - 屏1：市场概览（指数、温度计、资金全景）
  - 屏2：AI市场研判（大盘判断、风险、机会板块、操作建议）
  - 屏3：K线+策略信号（多周期K线、买卖点标注、策略信号叠加）
  - 屏4：实时监控预警（异常波动、资金异动、信号触发、新闻事件）
  - 屏5：组合管理（持仓、收益归因、风险暴露、再平衡建议）
  - 屏6：AI研究员（行业分析、因子挖掘、策略生成）

#### 模块②：市场温度指标
- **市场温度计**（0-100）：综合估值、情绪、资金、技术四维度
  - < 30：极度悲观（抄底区间）
  - 30-50：偏冷（逐步建仓）
  - 50-70：正常（持仓为主）
  - 70-85：偏热（逐步减仓）
  - > 85：过热（减仓/空仓）
- **分项指标**：估值温度、情绪温度、资金温度、技术温度各独立显示
- **历史温度曲线**：当前温度在历史分位数中的位置

#### 模块③：AI市场分析Agent
- **三大Agent协作**：
  - `MarketMacroAgent`：宏观环境研判（政策/流动性/外部冲击）
  - `SectorRotationAgent`：行业轮动分析（风格/板块/热点）
  - `StrategyAdvisorAgent`：策略建议（仓位/行业配置/策略推荐）
- **输出格式**：参照用户Mockup —— 大盘判断 + 风险评级 + 机会板块 + 操作建议 + AI综合评分

#### 模块④：多因子股票评分模型
- **五大因子维度**（已有基础，需升级）：
  - 估值因子：PE_TTM、PB、PS、EV/EBITDA、股息率
  - 质量因子：ROE、ROA、毛利率、净利率、资产负债率
  - 动量因子：1M/3M/6M/12M 收益、均线乖离率
  - 波动因子：波动率、Beta、最大回撤、下行风险
  - 情绪因子：北向资金变化、融资余额变化、分析师预期调整
- **评分模型**：因子标准化 → IC加权 → 综合打分 → 百分位排名
- **输出**：个股雷达图 + 行业排名 + 多空组合

#### 模块⑤：资金流分析
- **A股资金全景图**（已有 asfund 数据，需升级可视化）：
  - 主力资金净流入/流出（日/周/月）
  - 超大单/大单/中单/小单拆解
  - 北向资金（沪股通/深股通）
  - 融资融券余额变化
  - 行业资金流向热力图
  - 个股资金流排名

#### 模块⑥：策略回测系统（升级）
- **已有**：6种单策略回测（MA双均线/动量/反转/特质波动率/均线收敛/ICU均线择时）
- **新增**：
  - 策略组合回测（多策略并行+等权/IC加权/波动率倒数加权）
  - 参数优化（网格搜索/贝叶斯优化）
  - 压力测试（极端行情/黑天鹅场景）
  - 绩效归因（Brinson归因/Fama-French因子归因）

#### 模块⑦：实时监控预警
- **四类预警**：
  - 技术信号预警：突破均线/MACD金叉死叉/RSI超买超卖
  - 资金异动预警：主力大单/北向异常/融资异常
  - 事件驱动预警：新闻舆情突变/业绩预告/公告事件
  - 风控预警：回撤超限/集中度超限/VaR超限
- **推送方式**：WebSocket实时推送 + 页面弹窗 + 声音提醒

#### 模块⑧：组合管理
- **当前**：Mock持仓4只
- **目标**：
  - 真实模拟账户（初始100万+实时计算）
  - 持仓分析（行业分布/市值分布/风格暴露）
  - 风险指标（波动率/最大回撤/VaR/CVaR/夏普）
  - 再平衡建议（偏离度/调仓方案）
  - 交易记录（历史订单+成交明细）

#### 模块⑨：AI量化研究员
- **已有**：AI研究员（单一LLM对话）
- **升级为多Agent流水线**：
  - `IndustryAnalyst`：行业景气度 → 赛道选择
  - `FactorEngineer`：因子挖掘 → 因子测试 → 因子组合
  - `StrategyBuilder`：因子信号 → 择时规则 → 策略代码
  - `BacktestRunner`：自动化回测 → 绩效报告
  - `PortfolioOptimizer`：组合优化 → 权重分配

#### 模块⑩：专业金融终端UI
- **参照**：Wind终端 / 同花顺iFinD / Bloomberg
- **特点**：
  - 深色主题（#0b0f19背景）
  - 多屏可拖拽布局（Grid Layout + 自定义工作区）
  - 数据密度高（单屏展示更多信息）
  - 专业字体（JetBrains Mono/Tabular Numbers）
  - 快捷键支持（F5刷新 / Esc关闭 / Ctrl+K搜索）
  - 颜色规范：涨红跌绿（A股习惯）、涨绿跌红（国际习惯，可切换）

---

## 二、前端页面改造方案

### 2.1 整体布局重构

```
┌──────────────────────────────────────────────────────────┐
│ TopBar: 连接状态 · 当前时间 · 市场状态指示灯 · 搜索 · 通知  │
├──────┬───────────────────────────────────┬────────────────┤
│      │  ┌─────────────┐ ┌─────────────┐ │ 实时信号流      │
│      │  │ 市场温度计   │ │ AI市场研判  │ │ ⚡ 09:35 宁德.. │
│      │  │ 68/100      │ │ 震荡偏强    │ │ ⚡ 09:38 茅台.. │
│ Side │  │ 正常区间     │ │ ⭐⭐⭐☆☆    │ │ ⚡ 09:42 ...    │
│ bar  │  └─────────────┘ └─────────────┘ │                │
│      │  ┌──────────────────────────────┐│ 持仓概览        │
│ 导航  │  │ K线图表 + 策略信号叠加       ││ 总资产 ¥1.85M   │
│      │  │ [多周期切换][多标的切换]     ││ 今日 +1.29%     │
│      │  │ [买卖点标注][策略标注]       ││ 夏普 1.86       │
│      │  └──────────────────────────────┘│                │
│      │  ┌──────────────┐ ┌─────────────┤ 预警中心        │
│      │  │ 行业资金流向 │ │ 因子雷达图   │ 🟡 回撤预警     │
│      │  │ 热力图      │ │ 5维评分      │ 🟢 突破信号     │
│      │  └──────────────┘ └─────────────┘│                │
│      │  ┌──────────────────────────────────────────────┐  │
│      │  │ 标签页切换: AI研究员 | 策略回测 | 组合管理 | 交易记录 │  │
│      │  └──────────────────────────────────────────────┘  │
├──────┴───────────────────────────────────┴────────────────┤
│ StatusBar: 数据延迟 · 最后更新 · 内存/CPU · 快捷键提示       │
└──────────────────────────────────────────────────────────┘
```

### 2.2 页面改造清单

| 现有页面 | 改造成 | 说明 |
|---------|--------|------|
| `/dashboard` | **全面重写** | 六屏矩阵布局，所有Mock数据替换为真实数据 |
| `/strategies` | 保留并增强 | 增加策略矩阵对比、参数优化UI |
| `/ai-researcher` | **全面重写** | 多Agent流水线UI + 行业/因子/策略生成 |
| `/stock-analysis` | 保留并增强 | 增加多因子评分雷达图、资金流向图 |
| `/news` | 合并至Dashboard | 新闻流入实时信号流 |
| `/backtest` | 保留并增强 | 增加组合回测、压力测试、参数优化 |
| `/factor-research` | 保留并增强 | 增加因子IC热力图、多空收益曲线 |
| `/stock-picker` | 保留 | 已较完善 |
| `/market-dynamics` | 合并至Dashboard | 板块排名、龙虎榜、资金流融入首页 |
| `/trading` | **全面重写** | 真实模拟账户、订单管理、风控面板 |
| **(NEW)** `/portfolio` | **新增** | 组合管理：持仓/归因/再平衡/风险 |
| **(NEW)** `/alerts` | **新增** | 预警中心：全部预警统一管理 |
| **(NEW)** `/market-temperature` | **新增** | 市场温度专题页（含历史曲线） |

### 2.3 新增组件清单

| 组件 | 文件 | 用途 |
|------|------|------|
| `MarketThermometer` | `ui/MarketThermometer.tsx` | 市场温度计（0-100弧形仪表盘） |
| `AIMarketJudgment` | `ui/AIMarketJudgment.tsx` | AI市场研判卡片（5维度评分+建议） |
| `SectorHeatmap` | `charts/SectorHeatmap.tsx` | 行业资金流向热力图 |
| `FactorRadar` | `charts/FactorRadar.tsx` | 多因子评分雷达图 |
| `AlertStream` | `ui/AlertStream.tsx` | 实时预警信息流 |
| `PortfolioOverview` | `ui/PortfolioOverview.tsx` | 组合概览仪表板 |
| `StrategyMatrix` | `ui/StrategyMatrix.tsx` | 策略矩阵对比表 |
| `AgentPipeline` | `ui/AgentPipeline.tsx` | AI Agent流水线可视化 |
| `DashboardGrid` | `layout/DashboardGrid.tsx` | 可拖拽多屏Grid布局 |
| `StatusBar` | `layout/StatusBar.tsx` | 底部状态栏 |

---

## 三、后端接口设计

### 3.1 新增服务

| 服务 | 文件 | 职责 |
|------|------|------|
| `market_temperature_service` | `services/market_temperature_service.py` | 市场温度计算（估值/情绪/资金/技术四维） |
| `multi_factor_service` | `services/multi_factor_service.py` | 多因子评分（5维度+IC加权+百分位排名） |
| `alert_engine` | `services/alert_engine.py` | 预警引擎（技术/资金/事件/风控4类） |
| `portfolio_service` | `services/portfolio_service.py` | 组合管理（持仓/归因/再平衡/风险） |
| `ai_agent_service` | `services/ai_agent_service.py` | 多Agent编排（MarketMacro/SectorRotation/StrategyAdvisor） |
| `strategy_optimizer` | `services/strategy_optimizer.py` | 策略参数优化（网格搜索/贝叶斯） |
| `capital_flow_service` | `services/capital_flow_service.py` | 资金流分析（已有asfund，升级聚合） |

### 3.2 新增/升级API端点

```
# ===== 市场温度 =====
GET  /api/market-temperature          → 市场温度（当前+历史分位数+四维拆解）
GET  /api/market-temperature/history  → 历史温度时间序列

# ===== AI市场研判（多Agent） =====
POST /api/ai-agent/market-judgment    → 今日市场研判（大盘/风险/机会/建议/评分）
POST /api/ai-agent/sector-analysis    → 行业板块AI分析
POST /api/ai-agent/strategy-advisor   → AI策略建议

# ===== 多因子评分 =====
GET  /api/multi-factor/score?code=    → 单只股票多因子评分
POST /api/multi-factor/batch          → 批量评分（输入股票列表）
GET  /api/multi-factor/ranking        → 全市场/行业因子排名
GET  /api/multi-factor/ic-analysis    → 因子IC分析

# ===== 实时监控预警 =====
GET  /api/alerts                      → 当前预警列表
GET  /api/alerts/config               → 预警规则配置
PUT  /api/alerts/config               → 更新预警规则
WS   /ws/alerts                       → 实时预警推送

# ===== 组合管理 =====
GET  /api/portfolio/overview          → 组合概览（总资产/收益/风险）
GET  /api/portfolio/positions         → 当前持仓
GET  /api/portfolio/attribution       → 收益归因（Brinson）
GET  /api/portfolio/risk              → 风险指标（VaR/CVaR/波动率）
POST /api/portfolio/rebalance         → 再平衡建议
POST /api/portfolio/order             → 模拟下单
GET  /api/portfolio/orders            → 订单历史
DELETE /api/portfolio/order/{id}      → 撤单

# ===== Dashboard V2 =====
GET  /api/dashboard/v2                → Dashboard全量数据（新版，真数据）
WS   /ws/dashboard                    → Dashboard实时数据推送

# ===== 策略回测升级 =====
POST /api/backtest/optimize           → 参数优化
POST /api/backtest/portfolio          → 组合回测
GET  /api/backtest/stress-test        → 压力测试

# ===== 资金流升级 =====
GET  /api/capital-flow/overview       → 资金流全景（主力/北向/融资）
GET  /api/capital-flow/sector         → 行业资金流向
GET  /api/capital-flow/stock/{code}   → 个股资金流明细
```

### 3.3 WebSocket频道设计

| 频道 | 路径 | 推送内容 | 频率 |
|------|------|---------|------|
| market | `/ws/market` (已有) | 指数行情+自选股快照 | 5s |
| alerts | `/ws/alerts` (新增) | 预警触发通知 | 实时 |
| dashboard | `/ws/dashboard` (新增) | Dashboard全量更新 | 10s |
| signals | `/ws/signals` (新增) | 策略信号 | 实时 |

---

## 四、数据库设计

### 4.1 新增/升级表

```sql
-- ===== 市场温度记录（时间序列） =====
CREATE TABLE market_temperature (
    id          SERIAL PRIMARY KEY,
    date        DATE NOT NULL UNIQUE,
    score       FLOAT,               -- 0-100 综合温度
    valuation   FLOAT,               -- 估值温度
    sentiment   FLOAT,               -- 情绪温度
    capital     FLOAT,               -- 资金温度
    technical   FLOAT,               -- 技术温度
    risk_level  VARCHAR(20),          -- low/medium/high/extreme
    ai_judgment TEXT,                -- AI市场研判
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ===== 多因子评分 =====
CREATE TABLE factor_scores (
    id          SERIAL PRIMARY KEY,
    date        DATE NOT NULL,
    code        VARCHAR(20) NOT NULL,
    total_score FLOAT,               -- 综合评分(0-100)
    percentile  FLOAT,               -- 全市场百分位
    value_score FLOAT,               -- 估值因子分
    quality_score FLOAT,             -- 质量因子分
    momentum_score FLOAT,            -- 动量因子分
    volatility_score FLOAT,          -- 波动因子分
    sentiment_score FLOAT,           -- 情绪因子分
    detail      JSONB,               -- 各因子原始值+标准化值
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, code)
);
CREATE INDEX idx_factor_scores_date ON factor_scores(date);
CREATE INDEX idx_factor_scores_code ON factor_scores(code);

-- ===== 预警记录 =====
CREATE TABLE alerts (
    id          SERIAL PRIMARY KEY,
    type        VARCHAR(30) NOT NULL, -- technical/capital/event/risk
    severity    VARCHAR(10) NOT NULL, -- info/warning/critical
    code        VARCHAR(20),
    title       VARCHAR(200),
    message     TEXT,
    trigger_condition TEXT,          -- 触发条件描述
    is_read     BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_alerts_type ON alerts(type);
CREATE INDEX idx_alerts_created ON alerts(created_at DESC);

-- ===== 预警规则配置 =====
CREATE TABLE alert_rules (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100),
    type        VARCHAR(30),          -- technical/capital/event/risk
    condition   JSONB,               -- 触发条件配置
    enabled     BOOLEAN DEFAULT TRUE,
    cooldown_min INTEGER DEFAULT 5,  -- 冷却时间（分钟）
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ===== AI市场研判记录 =====
CREATE TABLE ai_market_judgments (
    id          SERIAL PRIMARY KEY,
    date        DATE NOT NULL UNIQUE,
    market_trend VARCHAR(30),        -- 大盘判断（强势/震荡偏强/震荡/震荡偏弱/弱势）
    risk_stars  INTEGER,             -- 风险星级(1-5)
    opportunities JSONB,             -- 机会板块列表
    advice      TEXT,                -- 操作建议
    ai_score    INTEGER,             -- AI综合评分(0-100)
    dimensions  JSONB,               -- 五维度评分详情
    buy_probability TEXT,            -- 买入概率描述
    generated_by VARCHAR(50),        -- 生成Agent名称
    model       VARCHAR(50),         -- LLM模型
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ===== 模拟组合 =====
CREATE TABLE portfolio_positions (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(20) NOT NULL UNIQUE,
    name        VARCHAR(50),
    shares      INTEGER,
    avg_cost    FLOAT,               -- 平均成本
    current_price FLOAT,
    market_value FLOAT,
    weight      FLOAT,               -- 权重(%)
    unrealized_pnl FLOAT,
    unrealized_pnl_pct FLOAT,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE portfolio_orders (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(20) NOT NULL,
    name        VARCHAR(50),
    direction   VARCHAR(10),          -- buy/sell
    price       FLOAT,
    shares      INTEGER,
    amount      FLOAT,
    status      VARCHAR(20),          -- pending/filled/cancelled
    reason      TEXT,                -- 交易理由
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE portfolio_snapshots (
    id          SERIAL PRIMARY KEY,
    date        DATE NOT NULL UNIQUE,
    total_value FLOAT,
    cash        FLOAT,
    position_value FLOAT,
    daily_pnl   FLOAT,
    daily_pnl_pct FLOAT,
    cumulative_pnl FLOAT,
    cumulative_pnl_pct FLOAT,
    positions   JSONB,               -- 当日持仓快照
    metrics     JSONB,               -- 风险指标快照
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ===== AI Agent任务记录 =====
CREATE TABLE agent_tasks (
    id          SERIAL PRIMARY KEY,
    agent_name  VARCHAR(50),         -- MarketMacro/SectorRotation/StrategyAdvisor/...
    task_type   VARCHAR(50),         -- market_judgment/sector_analysis/strategy_generation
    input_data  JSONB,
    output_data JSONB,
    status      VARCHAR(20) DEFAULT 'pending',  -- pending/running/completed/failed
    error_msg   TEXT,
    model       VARCHAR(50),
    tokens_used INTEGER,
    created_at  TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### 4.2 数据流架构

```
westock-data CLI ──→ westock_client ──→ 各service ──→ API Router ──→ 前端
                                        │
                                        ├── market_temperature_service (估值/情绪/资金/技术)
                                        ├── multi_factor_service (因子计算+评分)
                                        ├── alert_engine (规则匹配+推送)
                                        ├── ai_agent_service (LLM Agent编排)
                                        ├── portfolio_service (模拟账户+组合管理)
                                        └── capital_flow_service (资金流聚合)

WebSocket Manager ──→ /ws/market (已有)
                  ──→ /ws/alerts (新增)
                  ──→ /ws/dashboard (新增)
                  ──→ /ws/signals (新增)
```

---

## 五、代码修改方案（分阶段实施）

### Phase 1：基础设施（2-3天）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/market_temperature_service.py` | **新增** | 市场温度四维计算 |
| `backend/app/services/ai_agent_service.py` | **新增** | 三Agent编排（MarketMacro/SectorRotation/StrategyAdvisor） |
| `backend/app/services/alert_engine.py` | **新增** | 预警引擎核心 |
| `backend/app/routers/market_temperature.py` | **新增** | 市场温度API |
| `backend/app/routers/ai_agent.py` | **新增** | AI Agent API |
| `backend/app/routers/alerts.py` | **新增** | 预警API |
| `backend/app/db/models.py` | **修改** | 新增7张表 |
| `backend/app/db/database.py` | **修改** | init_db 建新表 |
| `backend/app/main.py` | **修改** | 挂载新路由+新WS端点 |

### Phase 2：Dashboard V2（2-3天）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/routers/dashboard.py` | **修改** | 新增 `/v2` 端点，全量真数据 |
| `frontend/src/app/dashboard/page.tsx` | **全面重写** | 六屏矩阵布局 |
| `frontend/src/components/ui/MarketThermometer.tsx` | **新增** | 市场温度计组件 |
| `frontend/src/components/ui/AIMarketJudgment.tsx` | **新增** | AI研判卡片 |
| `frontend/src/components/ui/AlertStream.tsx` | **新增** | 实时预警流 |
| `frontend/src/components/layout/DashboardGrid.tsx` | **新增** | 可拖拽Grid |
| `frontend/src/components/layout/StatusBar.tsx` | **新增** | 状态栏 |
| `frontend/src/lib/api.ts` | **修改** | 新增类型+API函数 |

### Phase 3：多因子+资金流（2天）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/multi_factor_service.py` | **新增** | 多因子评分引擎 |
| `backend/app/routers/multi_factor.py` | **新增** | 评分API |
| `frontend/src/components/charts/FactorRadar.tsx` | **新增** | 因子雷达图 |
| `frontend/src/components/charts/SectorHeatmap.tsx` | **新增** | 资金流热力图 |
| `frontend/src/app/factor-research/page.tsx` | **修改** | 增加因子IC热力图、多空收益 |
| `frontend/src/app/stock-analysis/page.tsx` | **修改** | 增加因子评分雷达图 |

### Phase 4：组合管理+预警（2天）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/portfolio_service.py` | **新增** | 组合管理核心 |
| `backend/app/routers/portfolio.py` | **新增** | 组合管理API |
| `frontend/src/app/portfolio/page.tsx` | **新增** | 组合管理页面 |
| `frontend/src/app/alerts/page.tsx` | **新增** | 预警中心页面 |
| `frontend/src/components/ui/PortfolioOverview.tsx` | **新增** | 组合概览 |
| `frontend/src/app/trading/page.tsx` | **重写** | 真实模拟账户 |

### Phase 5：策略系统升级+UI收尾（2天）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/strategy_optimizer.py` | **新增** | 参数优化 |
| `backend/app/routers/backtest.py` | **修改** | 新增 optimize/portfolio/stress-test |
| `frontend/src/app/ai-researcher/page.tsx` | **重写** | 多Agent流水线UI |
| `frontend/src/components/ui/AgentPipeline.tsx` | **新增** | Agent流水线可视化 |
| `frontend/src/components/ui/StrategyMatrix.tsx` | **新增** | 策略矩阵对比 |
| `frontend/src/components/layout/Sidebar.tsx` | **修改** | 导航结构优化 |
| `frontend/src/app/layout.tsx` | **修改** | 主题/字体/全局样式 |

---

## 六、技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| Dashboard布局方案 | CSS Grid + react-grid-layout | 可拖拽+响应式，专业终端习惯 |
| 实时数据 | WebSocket (已有) 扩展频道 | 低延迟，已跑通 |
| AI Agent框架 | 纯Python函数编排 + LLM调用 | 无额外依赖，与现有llm_service一致 |
| 因子计算 | pandas + scipy（已有） | 本地计算，不依赖外部因子库 |
| 图表库 | ECharts (已有echarts-for-react) | 专业金融图表，已集成 |
| 数据库 | SQLite (开发) → PostgreSQL (生产) | 已有database.py支持切换 |
| 模拟账户 | 内存+SQLite持久化 | 简单可靠，无需外部券商接口 |

---

## 七、风险与注意事项

1. **数据源依赖**：westock-data 所有数据来自东方财富公开接口，非官方交易所数据，可能有延迟
2. **LLM成本**：多Agent模式下DeepSeek API调用量显著增加，需监控token消耗
3. **实时性**：westock-data走HTTP CLI调用，非实时行情，延迟约秒级
4. **因子覆盖**：多因子模型依赖财务报表数据（季报频率），非高频因子
5. **模拟交易**：不接入实际券商，所有交易均为模拟

---

> ⚠️ 以上方案由 AI 基于系统现状分析生成，仅供参考。实施时需根据实际开发资源调整优先级和范围。所有量化策略结果均为模型驱动，不构成投资建议。
