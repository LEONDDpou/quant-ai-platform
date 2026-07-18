# v1.3.1 交付概览

## 版本：1.3.0 → 1.3.1

---

## 三项优化交付

### 1. 侧边栏入口 — 机构聚合独立页面
- **Sidebar** 分析工具分组新增「机构动向」入口（Building2 图标）
- **新建 `/institution` 页面**：五大模块
  - 机构交易活跃度圆环仪表（0-100 评分+三级评级）
  - 北向资金净流向卡片
  - 主力资金结构柱状对比
  - 龙虎榜机构席位透视表（含代码/席位/买入/净买/占比，可点击跳转详情）
  - 机构持仓特征（热门板块+冷门板块+净买入TOP）

### 2. 数据贯通 — 机构数据接入分析页
- **stock-analysis 页**：左侧面板新增「机构动向快览」卡片
  - 活跃度进度条、北向资金、主力方向、龙虎榜净买入 TOP3
- **ai-researcher 页**：报告 Tab 下方新增四维机构动向卡片
  - 活跃度/北向/主力方向/龙虎榜 TOP3 一目了然

### 3. 更多实时指标 — 涨跌家数/市场宽度/涨跌停
- **后端新增**：`market_dynamics_service.py` → `get_market_breadth()`
  - 调用 `westock-data changedist` 聚合沪深两市数据
  - 涨跌家数、涨跌停数、分布区间全量统计
- **新增路由**：`GET /api/market-dynamics/a-share/breadth`
- **前端 MarketBreadthCard 组件**：
  - 上涨/平盘/下跌三宫格 KPI
  - 涨跌比彩色进度条
  - 涨停/跌停统计双栏
  - 沪深分市场明细
  - 市场宽度智能评级（强势普涨/偏强/均衡/偏弱/弱势普跌）

---

## 验证状态
- ✅ TypeScript 零错误
- ✅ Next.js 16 路由全量编译通过（含新 `/institution`）
- ✅ 后端 Python 语法编译通过
- ✅ 版本号三处统一升级到 1.3.1

## 改动文件清单
| 文件 | 操作 |
|------|------|
| `backend/app/services/market_dynamics_service.py` | 新增 get_market_breadth() |
| `backend/app/routers/market_dynamics.py` | 新增 /a-share/breadth 端点 |
| `backend/app/main.py` | 版本 1.3.0 → 1.3.1 |
| `frontend/src/components/layout/Sidebar.tsx` | 新增机构动向导航项 |
| `frontend/src/app/institution/page.tsx` | 新建机构聚合独立页面 |
| `frontend/src/app/stock-analysis/page.tsx` | 新增机构动向快览卡片 |
| `frontend/src/app/ai-researcher/page.tsx` | 新增机构动向四维卡片 |
| `frontend/src/app/market-dynamics/page.tsx` | 新增 MarketBreadthCard 组件 |
| `frontend/src/lib/api.ts` | 新增 MarketBreadth 类型 + API 函数 |

> ⚠️ 以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。投资有风险，决策需谨慎。
