"use client";

import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  Wallet,
  Plus,
  RefreshCw,
  CandlestickChart,
  Layers,
  Activity,
  Radio,
  TrendingUp,
  TrendingDown,
  Wifi,
  WifiOff,
  ShoppingCart,
  Briefcase,
  X,
  CheckCircle2,
  Clock,
  Ban,
  AlertTriangle,
  LineChart,
  Camera,
} from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { cn, formatCurrency, formatPct, formatNumber, getColorClass } from "@/lib/utils";
import {
  fetchPaperAccounts,
  createPaperAccount,
  fetchPaperAccountMetrics,
  fetchPaperOrderBook,
  fetchPaperKline,
  fetchPaperSectors,
  fetchPaperMarketStatus,
  createPaperOrder,
  fetchPaperOrders,
  cancelPaperOrder,
  fetchPaperPositions,
  rolloverPaperDay,
  matchPaperOrders,
  fetchPaperPositionSummary,
  refreshPaperPositions,
  type PaperAccount,
  type PaperAccountMetrics,
  type PaperQuote,
  type PaperOrderBook,
  type PaperKline,
  type PaperSector,
  type PaperMarketStatus,
  type PaperOrder,
  type PaperPosition,
  type PaperPositionSummary,
  type PaperOrderType,
  fetchPaperEquity,
  fetchPaperStatistics,
  takePaperSnapshot,
  refreshPaperStats,
  type PaperEquityPoint,
  type PaperAccountStatistics,
} from "@/lib/api";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { AITradingPanel } from "@/components/AITradingPanel";
import { BacktestPanel } from "@/components/BacktestPanel";
import { RiskCenterPanel } from "@/components/RiskCenterPanel";
import StockPoolPanel from "@/components/StockPoolPanel";
import ResearcherAgentPanel from "@/components/ResearcherAgentPanel";
import StrategyMarketplacePanel from "@/components/StrategyMarketplacePanel";
import PortfolioPanel from "@/components/PortfolioPanel";
import DailyReviewPanel from "@/components/DailyReviewPanel";
import AccountOverviewPanel from "@/components/AccountOverviewPanel";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import { API_BASE } from "@/lib/config";

// 关注池（与后端 WATCHLIST 保持一致）
const WATCHLIST = ["600519", "300750", "601318", "000858", "600036", "002594"];
const KLINE_PERIODS = [
  { key: "1m", label: "1分" },
  { key: "5m", label: "5分" },
  { key: "15m", label: "15分" },
  { key: "30m", label: "30分" },
  { key: "60m", label: "60分" },
  { key: "day", label: "日K" },
  { key: "week", label: "周K" },
  { key: "month", label: "月K" },
];

// ============================================================
// 工具
// ============================================================
const pct = (n: number) => formatPct(n);
const cur = (n: number) => formatCurrency(n);

// ============================================================
// 账户管理面板
// ============================================================
function AccountPanel({
  accounts,
  selectedId,
  onSelect,
  metrics,
  creating,
  onStartCreate,
  onCreate,
}: {
  accounts: PaperAccount[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  metrics: PaperAccountMetrics | null;
  creating: boolean;
  onStartCreate: () => void;
  onCreate: (name: string, preset: string, capital: number) => void;
}) {
  const [name, setName] = useState("");
  const [preset, setPreset] = useState("100万");
  const [capital, setCapital] = useState(1000000);
  const presets = [
    { key: "100万", val: 1000000 },
    { key: "500万", val: 5000000 },
    { key: "1000万", val: 10000000 },
    { key: "custom", val: -1 },
  ];

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Wallet className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">模拟账户</h3>
        <button className="btn-ghost ml-auto flex items-center gap-1" onClick={onStartCreate}>
          <Plus className="w-3.5 h-3.5" /> 新建
        </button>
      </div>

      {creating && (
        <div className="bg-[#0b1120] border border-[#1e2a3d] rounded-lg p-3 space-y-2">
          <input
            className="input-dark"
            placeholder="账户名称（如：稳健一号）"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="grid grid-cols-4 gap-1.5">
            {presets.map((p) => (
              <button
                key={p.key}
                className={cn(
                  "text-[11px] py-1.5 rounded-md border transition-colors",
                  preset === p.key
                    ? "border-cyan-500/60 bg-cyan-900/20 text-cyan-300"
                    : "border-[#1e2a3d] text-slate-400 hover:bg-white/5"
                )}
                onClick={() => {
                  setPreset(p.key);
                  if (p.val > 0) setCapital(p.val);
                }}
              >
                {p.key}
              </button>
            ))}
          </div>
          {preset === "custom" && (
            <input
              className="input-dark"
              type="number"
              placeholder="初始资金（元）"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value) || 0)}
            />
          )}
          <div className="flex gap-2 pt-1">
            <button
              className="btn-primary flex-1"
              disabled={!name.trim() || capital <= 0}
              onClick={() => onCreate(name.trim(), preset, capital)}
            >
              创建账户
            </button>
            <button className="btn-secondary" onClick={onStartCreate}>
              取消
            </button>
          </div>
        </div>
      )}

      {/* 账户列表 */}
      <div className="space-y-1.5 max-h-[240px] overflow-y-auto">
        {accounts.length === 0 && (
          <div className="text-xs text-slate-600 py-4 text-center">暂无模拟账户，点击「新建」创建</div>
        )}
        {accounts.map((a) => (
          <button
            key={a.id}
            onClick={() => onSelect(a.id)}
            className={cn(
              "w-full text-left rounded-lg px-3 py-2 border transition-all",
              selectedId === a.id
                ? "border-cyan-500/50 bg-cyan-900/10"
                : "border-[#151d2e] hover:bg-white/[0.03]"
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-200 font-medium">{a.name}</span>
              <span className={cn("text-[11px] font-mono", getColorClass(a.totalPnl))}>
                {pct(a.totalPnlPct)}
              </span>
            </div>
            <div className="flex items-center justify-between mt-0.5">
              <span className="text-[10px] text-slate-500 font-mono">总资产 {cur(a.totalAssets)}</span>
              <span className="text-[10px] text-slate-600">{a.status === "active" ? "进行中" : a.status}</span>
            </div>
          </button>
        ))}
      </div>

      {/* 选中账户指标 */}
      {metrics && (
        <div className="border-t border-[#151d2e] pt-3 grid grid-cols-2 gap-x-3 gap-y-2">
          <Metric label="总资产" value={cur(metrics.totalAssets)} />
          <Metric label="可用资金" value={cur(metrics.availableCash)} />
          <Metric label="持仓市值" value={cur(metrics.positionValue)} />
          <Metric label="仓位比例" value={metrics.positionRatio.toFixed(1) + "%"} />
          <Metric label="总收益" value={cur(metrics.totalPnl)} cls={getColorClass(metrics.totalPnl)} />
          <Metric label="累计收益率" value={pct(metrics.totalPnlPct)} cls={getColorClass(metrics.totalPnl)} />
          <Metric label="今日收益" value={cur(metrics.todayPnl)} cls={getColorClass(metrics.todayPnl)} />
          <Metric label="今日收益率" value={pct(metrics.todayPnlPct)} cls={getColorClass(metrics.todayPnl)} />
          <Metric label="最大回撤" value={metrics.maxDrawdown.toFixed(2) + "%"} />
          <Metric label="夏普比率" value={metrics.sharpeRatio.toFixed(2)} />
          <Metric label="胜率" value={metrics.winRate.toFixed(1) + "%"} />
          <Metric label="盈亏比" value={metrics.profitLossRatio.toFixed(2)} />
        </div>
      )}
      {!metrics && selectedId && (
        <div className="border-t border-[#151d2e] pt-3 text-xs text-slate-600 text-center">加载账户指标…</div>
      )}
    </div>
  );
}

function Metric({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div>
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={cn("text-sm font-mono font-semibold text-slate-200", cls)}>{value}</div>
    </div>
  );
}

// ============================================================
// 行情中心 — 关注池实时行情（WebSocket）
// ============================================================
function WatchlistPanel({
  quotes,
  selectedCode,
  onSelect,
  live,
}: {
  quotes: Record<string, PaperQuote>;
  selectedCode: string;
  onSelect: (code: string) => void;
  live: boolean;
}) {
  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Activity className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">关注池实时行情</h3>
        <span
          className={cn(
            "badge ml-auto text-[10px]",
            live ? "badge-live" : "badge-gray"
          )}
        >
          {live ? "实时推送" : "未连接"}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table text-[11px]">
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th className="text-right">最新价</th>
              <th className="text-right">涨跌幅</th>
              <th className="text-right">换手</th>
            </tr>
          </thead>
          <tbody>
            {WATCHLIST.map((code) => {
              const q = quotes[code];
              const up = (q?.changePct ?? 0) >= 0;
              return (
                <tr
                  key={code}
                  onClick={() => onSelect(code)}
                  className={cn(
                    "cursor-pointer",
                    selectedCode === code && "bg-cyan-900/10"
                  )}
                >
                  <td className="font-mono text-slate-400">{code}</td>
                  <td className="text-slate-200">{q?.name ?? "—"}</td>
                  <td className={cn("text-right font-mono", q ? (up ? "text-emerald-400" : "text-red-400") : "text-slate-500")}>
                    {q ? q.price.toFixed(2) : "—"}
                  </td>
                  <td className={cn("text-right font-mono", q ? (up ? "text-emerald-400" : "text-red-400") : "text-slate-500")}>
                    {q ? pct(q.changePct) : "—"}
                  </td>
                  <td className="text-right font-mono text-slate-500">
                    {q ? q.turnover.toFixed(2) + "%" : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// 五档盘口
// ============================================================
function OrderBookPanel({ ob }: { ob: PaperOrderBook | null }) {
  if (!ob) {
    return (
      <div className="card p-4 flex items-center justify-center text-slate-600 text-xs h-full">
        选择标的查看五档盘口
      </div>
    );
  }
  const maxVol = Math.max(
    ...ob.bids.map((b) => b.volume),
    ...ob.asks.map((a) => a.volume),
    1
  );
  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Layers className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">五档盘口</h3>
        <span className="badge badge-gray ml-auto text-[10px]">{ob.code}</span>
      </div>
      <div className="space-y-0.5">
        {[...ob.asks].reverse().map((a, i) => (
          <Row key={"a" + i} side="ask" price={a.price} volume={a.volume} ratio={a.volume / maxVol} />
        ))}
        <div className="text-center text-[11px] font-mono py-0.5 text-slate-300 border-y border-[#1e2a3d]">
          {ob.name}
        </div>
        {ob.bids.map((b, i) => (
          <Row key={"b" + i} side="bid" price={b.price} volume={b.volume} ratio={b.volume / maxVol} />
        ))}
      </div>
      <div className="text-[10px] text-slate-600 text-right font-mono">
        数据源：{ob.dataSource === "akshare" ? "实时" : "模拟"}
      </div>
    </div>
  );
}

function Row({
  side,
  price,
  volume,
  ratio,
}: {
  side: "ask" | "bid";
  price: number;
  volume: number;
  ratio: number;
}) {
  const color = side === "ask" ? "bg-red-500/15" : "bg-emerald-500/15";
  return (
    <div className="relative flex items-center justify-between text-[11px] font-mono px-2 py-0.5">
      <div className={cn("absolute left-0 top-0 bottom-0", color)} style={{ width: `${ratio * 100}%` }} />
      <span className={cn("relative z-10", side === "ask" ? "text-red-400" : "text-emerald-400")}>
        {price.toFixed(2)}
      </span>
      <span className="relative z-10 text-slate-400">{formatNumber(volume, 0)}</span>
    </div>
  );
}

// ============================================================
// K 线（ECharts 蜡烛图）
// ============================================================
function KlinePanel({
  code,
  kline,
  period,
  onPeriod,
}: {
  code: string;
  kline: PaperKline | null;
  period: string;
  onPeriod: (p: string) => void;
}) {
  const option = useMemo<EChartsOption>(() => {
    if (!kline || kline.points.length === 0) return {};
    const dates = kline.points.map((p) => p.date);
    const data = kline.points.map((p) => [p.open, p.close, p.low, p.high]);
    return {
      backgroundColor: "transparent",
      grid: { left: 48, right: 12, top: 16, bottom: 24 },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: "#1e2a3d" } },
        axisLabel: { color: "#64748b", fontSize: 9 },
        boundaryGap: true,
      },
      yAxis: {
        scale: true,
        axisLine: { lineStyle: { color: "#1e2a3d" } },
        axisLabel: { color: "#64748b", fontSize: 9 },
        splitLine: { lineStyle: { color: "#0f1626" } },
      },
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
      series: [
        {
          type: "candlestick",
          data,
          itemStyle: {
            color: "#ef4444",
            color0: "#10b981",
            borderColor: "#ef4444",
            borderColor0: "#10b981",
          },
        },
      ],
    };
  }, [kline]);

  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <CandlestickChart className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">K 线</h3>
        <span className="badge badge-gray text-[10px] font-mono">{code}</span>
        <div className="flex gap-1 ml-auto flex-wrap">
          {KLINE_PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => onPeriod(p.key)}
              className={cn(
                "text-[10px] px-2 py-1 rounded-md border transition-colors",
                period === p.key
                  ? "border-cyan-500/60 bg-cyan-900/20 text-cyan-300"
                  : "border-[#1e2a3d] text-slate-400 hover:bg-white/5"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div className="h-[280px]">
        {kline && kline.points.length > 0 ? (
          <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge lazyUpdate />
        ) : (
          <div className="h-full flex items-center justify-center text-slate-600 text-xs">加载 K 线…</div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// 板块（行业 / 概念）
// ============================================================
function SectorPanel({ sectors, kind, onKind }: { sectors: PaperSector[]; kind: string; onKind: (k: "industry" | "concept") => void }) {
  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">板块涨幅</h3>
        <div className="flex gap-1 ml-auto">
          <button
            onClick={() => onKind("industry")}
            className={cn(
              "text-[10px] px-2 py-1 rounded-md border",
              kind === "industry" ? "border-cyan-500/60 bg-cyan-900/20 text-cyan-300" : "border-[#1e2a3d] text-slate-400"
            )}
          >
            行业
          </button>
          <button
            onClick={() => onKind("concept")}
            className={cn(
              "text-[10px] px-2 py-1 rounded-md border",
              kind === "concept" ? "border-cyan-500/60 bg-cyan-900/20 text-cyan-300" : "border-[#1e2a3d] text-slate-400"
            )}
          >
            概念
          </button>
        </div>
      </div>
      <div className="space-y-1 max-h-[260px] overflow-y-auto">
        {sectors.map((s) => {
          const up = s.changePct >= 0;
          return (
            <div key={s.code} className="flex items-center justify-between text-[11px]">
              <span className="text-slate-300">{s.name}</span>
              <span className="flex items-center gap-2">
                <span className="text-slate-600 text-[10px]">领涨 {s.leader}</span>
                <span className={cn("font-mono", up ? "text-emerald-400" : "text-red-400")}>
                  {pct(s.changePct)}
                </span>
              </span>
            </div>
          );
        })}
        {sectors.length === 0 && <div className="text-xs text-slate-600 text-center py-3">加载中…</div>}
      </div>
    </div>
  );
}

// ============================================================
// 订单状态徽标 (M3)
// ============================================================
const ORDER_STATUS_META: Record<
  string,
  { label: string; cls: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  pending: { label: "待成交", cls: "badge-yellow", Icon: Clock },
  partial: { label: "部分成交", cls: "badge-orange", Icon: Clock },
  filled: { label: "已成交", cls: "badge-green", Icon: CheckCircle2 },
  cancelled: { label: "已撤单", cls: "badge-gray", Icon: Ban },
  expired: { label: "已失效", cls: "badge-red", Icon: Ban },
};
function OrderStatusBadge({ status }: { status: string }) {
  const m = ORDER_STATUS_META[status] ?? { label: status, cls: "badge-gray", Icon: Clock };
  return (
    <span className={cn("badge text-[10px] flex items-center gap-1", m.cls)}>
      <m.Icon className="w-3 h-3" />
      {m.label}
    </span>
  );
}

// ============================================================
// 下单面板 (M3)
// ============================================================
function OrderPanel(props: {
  accountId: number | null;
  code: string;
  name: string;
  price: number;
  onSubmitted: () => void;
}) {
  const { accountId, code, name, price, onSubmitted } = props;
  const [direction, setDirection] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<"limit" | "market" | "stop_profit" | "stop_loss" | "grid">("limit");
  const [priceInput, setPriceInput] = useState("");
  const [qtyInput, setQtyInput] = useState("");
  const [trigger, setTrigger] = useState("");
  const [gridUpper, setGridUpper] = useState("");
  const [gridLower, setGridLower] = useState("");
  const [gridStep, setGridStep] = useState("");
  const [gridQty, setGridQty] = useState("");
  const [tranches, setTranches] = useState("1");
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const isGrid = orderType === "grid";
  const isStop = orderType === "stop_profit" || orderType === "stop_loss";
  const isMarket = orderType === "market";

  // 限价 / 条件单缺省带入当前价
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!isGrid && price > 0 && priceInput === "") setPriceInput(price.toFixed(2));
  }, [price, orderType]);

  const submit = async () => {
    if (accountId === null) return setMsg({ ok: false, text: "请先选择模拟账户" });
    const quantity = parseInt(qtyInput, 10);
    if (!Number.isInteger(quantity) || quantity <= 0) return setMsg({ ok: false, text: "数量需为正整数" });
    if (quantity % 100 !== 0) return setMsg({ ok: false, text: "数量需为 100 股整数倍" });
    const body: Parameters<typeof createPaperOrder>[0] = {
      accountId,
      code,
      name,
      direction,
      orderType: orderType as PaperOrderType,
      quantity,
    };
    if (!isMarket) body.price = parseFloat(priceInput) || parseFloat(trigger) || 0;
    if (isStop) body.triggerPrice = parseFloat(trigger) || 0;
    if (isGrid) {
      body.gridUpper = parseFloat(gridUpper) || 0;
      body.gridLower = parseFloat(gridLower) || 0;
      body.gridStep = parseFloat(gridStep) || 0;
      body.gridQtyPer = parseInt(gridQty, 10) || 0;
    }
    const t = parseInt(tranches, 10);
    if (t > 1) body.tranches = t;

    setSubmitting(true);
    setMsg(null);
    try {
      const res = await createPaperOrder(body);
      setMsg({ ok: true, text: `已提交 ${res.length} 笔订单` });
      setQtyInput("");
      onSubmitted();
    } catch (e: any) {
      setMsg({ ok: false, text: "下单失败：" + (e?.message ?? "未知错误") });
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    "w-full bg-[#0f1626] border border-[#1e2a3d] rounded-md px-2 py-1.5 text-[12px] font-mono text-slate-200 focus:border-cyan-500/60 outline-none";

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <ShoppingCart className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">下单</h3>
        <span className="badge badge-cyan ml-auto text-[10px] font-mono">{code}</span>
      </div>

      {/* 方向 */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => setDirection("buy")}
          className={cn(
            "text-[12px] py-1.5 rounded-md border transition-colors",
            direction === "buy"
              ? "border-emerald-500/60 bg-emerald-900/20 text-emerald-300"
              : "border-[#1e2a3d] text-slate-400 hover:bg-white/5"
          )}
        >
          买入
        </button>
        <button
          onClick={() => setDirection("sell")}
          className={cn(
            "text-[12px] py-1.5 rounded-md border transition-colors",
            direction === "sell"
              ? "border-red-500/60 bg-red-900/20 text-red-300"
              : "border-[#1e2a3d] text-slate-400 hover:bg-white/5"
          )}
        >
          卖出
        </button>
      </div>

      {/* 订单类型 */}
      <select
        value={orderType}
        onChange={(e) => setOrderType(e.target.value as typeof orderType)}
        className={cn(inputCls, "font-sans")}
      >
        <option value="limit">限价单</option>
        <option value="market">市价单</option>
        <option value="stop_profit">止盈单</option>
        <option value="stop_loss">止损单</option>
        <option value="grid">网格单</option>
      </select>

      {/* 价格 / 触发价 */}
      {!isGrid && (
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-slate-500">{isMarket ? "市价" : "委托价"}</span>
            <input
              className={inputCls}
              placeholder={isMarket ? "市价" : "0.00"}
              value={priceInput}
              disabled={isMarket}
              onChange={(e) => setPriceInput(e.target.value)}
            />
          </label>
          {isStop && (
            <label className="flex flex-col gap-1">
              <span className="text-[10px] text-slate-500">触发价</span>
              <input
                className={inputCls}
                placeholder="0.00"
                value={trigger}
                onChange={(e) => setTrigger(e.target.value)}
              />
            </label>
          )}
        </div>
      )}

      {/* 数量 / 分批 */}
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-slate-500">数量(股)</span>
          <input
            className={inputCls}
            placeholder="100"
            value={qtyInput}
            onChange={(e) => setQtyInput(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-slate-500">分批笔数</span>
          <input
            className={inputCls}
            placeholder="1"
            value={tranches}
            onChange={(e) => setTranches(e.target.value)}
          />
        </label>
      </div>

      {/* 网格参数 */}
      {isGrid && (
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-slate-500">上沿</span>
            <input className={inputCls} placeholder="0.00" value={gridUpper} onChange={(e) => setGridUpper(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-slate-500">下沿</span>
            <input className={inputCls} placeholder="0.00" value={gridLower} onChange={(e) => setGridLower(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-slate-500">步长</span>
            <input className={inputCls} placeholder="0.00" value={gridStep} onChange={(e) => setGridStep(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-slate-500">每格数量</span>
            <input className={inputCls} placeholder="100" value={gridQty} onChange={(e) => setGridQty(e.target.value)} />
          </label>
        </div>
      )}

      {msg && (
        <div className={cn("text-[11px]", msg.ok ? "text-emerald-400" : "text-red-400")}>{msg.text}</div>
      )}

      <button
        onClick={submit}
        disabled={submitting}
        className={cn(
          "w-full py-2 rounded-md text-[13px] font-medium transition-colors",
          submitting
            ? "bg-slate-700 text-slate-400 cursor-not-allowed"
            : direction === "buy"
            ? "bg-emerald-600 hover:bg-emerald-500 text-white"
            : "bg-red-600 hover:bg-red-500 text-white"
        )}
      >
        {submitting ? "提交中…" : `${direction === "buy" ? "买入" : "卖出"}委托`}
      </button>
      <p className="text-[10px] text-slate-600 leading-relaxed">
        A股规则：T+1 当日买入次日可卖；限价单需落在 ±10%(ST ±5% / 科创板 ±20%) 涨跌停内；手续费按 0.025%(最低5元)+ 印花税0.05%(仅卖出)+ 过户费0.001% 估算。
      </p>
    </div>
  );
}

// ============================================================
// 持仓面板 (M3)
// ============================================================
function PositionPanel(props: {
  positions: PaperPosition[];
  summary: PaperPositionSummary | null;
  onRefresh: () => void;
}) {
  const { positions, summary, onRefresh } = props;
  const pnlCls = (n: number) => (n >= 0 ? "text-emerald-400" : "text-red-400");
  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Briefcase className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">持仓管理</h3>
        <span className="badge badge-gray ml-auto text-[10px]">{positions.length} 只</span>
        <button
          onClick={onRefresh}
          className="badge badge-cyan text-[10px] cursor-pointer hover:opacity-80 flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" /> 刷新市值
        </button>
      </div>

      {/* 汇总卡片 */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <SummaryCard label="持仓市值" value={cur(summary.totalMarketValue)} />
          <SummaryCard label="浮动盈亏" value={cur(summary.unrealizedPnl)} sub={pct(summary.unrealizedPnlPct)} cls={pnlCls(summary.unrealizedPnl)} />
          <SummaryCard label="当日盈亏" value={cur(summary.todayPnl)} sub={pct(summary.todayPnlPct)} cls={pnlCls(summary.todayPnl)} />
          <SummaryCard label="已实现盈亏" value={cur(summary.realizedPnl)} cls={pnlCls(summary.realizedPnl)} />
          <SummaryCard label="总盈亏" value={cur(summary.totalPnl)} sub="浮动+已实现" cls={pnlCls(summary.totalPnl)} />
          <SummaryCard label="最大单一占比" value={pct(summary.maxPositionRatio)} sub={`前三大 ${pct(summary.top3Ratio)}`} />
        </div>
      )}

      {/* 集中度预警 */}
      {summary && summary.maxPositionRatio > 50 && (
        <div className="flex items-center gap-2 text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-1">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          单一持仓占比 {pct(summary.maxPositionRatio)} 偏高，注意集中度风险（前三大合计 {pct(summary.top3Ratio)}）
        </div>
      )}

      {/* 行业分布 */}
      {summary && summary.industryDistribution.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="text-[10px] text-slate-500">行业分布</div>
          {summary.industryDistribution.map((d) => (
            <div key={d.industry} className="flex items-center gap-2 text-[11px]">
              <span className="w-16 truncate text-slate-300">{d.industry}</span>
              <div className="flex-1 h-2 rounded bg-slate-700/50 overflow-hidden">
                <div className="h-full bg-cyan-500/70" style={{ width: `${Math.min(100, d.ratio)}%` }} />
              </div>
              <span className="w-12 text-right font-mono text-slate-400">{pct(d.ratio)}</span>
            </div>
          ))}
        </div>
      )}

      {/* 明细表 */}
      {positions.length === 0 ? (
        <div className="flex items-center justify-center text-slate-600 text-xs h-20">暂无持仓</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table text-[11px]">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th className="text-right">持股</th>
                <th className="text-right">可卖</th>
                <th className="text-right">成本</th>
                <th className="text-right">现价</th>
                <th className="text-right">市值</th>
                <th className="text-right">盈亏</th>
                <th className="text-right">%</th>
                <th className="text-right">天数</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const up = p.pnlAmount >= 0;
                return (
                  <tr key={p.code}>
                    <td className="font-mono text-slate-400">{p.code}</td>
                    <td className="text-slate-200">{p.name}</td>
                    <td className="text-right font-mono">{p.shares}</td>
                    <td className="text-right font-mono text-slate-400">{p.sellableShares}</td>
                    <td className="text-right font-mono">{p.costPrice.toFixed(2)}</td>
                    <td className="text-right font-mono">{p.currentPrice.toFixed(2)}</td>
                    <td className="text-right font-mono">{cur(p.marketValue)}</td>
                    <td className={cn("text-right font-mono", up ? "text-emerald-400" : "text-red-400")}>
                      {cur(p.pnlAmount)}
                    </td>
                    <td className={cn("text-right font-mono", up ? "text-emerald-400" : "text-red-400")}>
                      {pct(p.pnlPct)}
                    </td>
                    <td className="text-right font-mono text-slate-500">{p.holdDays}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, sub, cls }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div className="rounded border border-slate-700/50 bg-slate-800/30 px-2 py-1.5">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={cn("font-mono text-xs font-semibold", cls || "text-slate-200")}>{value}</div>
      {sub && <div className={cn("font-mono text-[10px]", cls || "text-slate-400")}>{sub}</div>}
    </div>
  );
}

// ============================================================
// 订单列表面板 (M3)
// ============================================================
function OrderListPanel(props: {
  orders: PaperOrder[];
  onCancel: (id: number) => void;
  onRefresh: () => void;
  onMatch: () => void;
  onRollover: () => void;
  busy: boolean;
}) {
  const { orders, onCancel, onRefresh, onMatch, onRollover, busy } = props;
  const [cancelling, setCancelling] = useState<number | null>(null);
  const doCancel = async (id: number) => {
    setCancelling(id);
    try {
      await onCancel(id);
    } finally {
      setCancelling(null);
    }
  };
  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <ShoppingCart className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">订单列表</h3>
        <div className="flex items-center gap-1 ml-auto flex-wrap">
          <button className="btn-ghost flex items-center gap-1" onClick={onMatch} disabled={busy}>
            <RefreshCw className={cn("w-3.5 h-3.5", busy && "animate-spin")} /> 撮合
          </button>
          <button className="btn-ghost flex items-center gap-1" onClick={onRollover} disabled={busy}>
            <Clock className="w-3.5 h-3.5" /> T+1 清算
          </button>
          <button className="btn-ghost flex items-center gap-1" onClick={onRefresh}>
            <RefreshCw className="w-3.5 h-3.5" /> 刷新
          </button>
          <span className="badge badge-gray text-[10px]">{orders.length} 笔</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table text-[11px]">
          <thead>
            <tr>
              <th>ID</th>
              <th>代码</th>
              <th>名称</th>
              <th>方向</th>
              <th>类型</th>
              <th className="text-right">委托价</th>
              <th className="text-right">数量</th>
              <th className="text-right">成交</th>
              <th>状态</th>
              <th>来源</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => {
              const canCancel = o.status === "pending" || o.status === "partial";
              return (
                <tr key={o.id}>
                  <td className="font-mono text-slate-500">{o.id}</td>
                  <td className="font-mono text-slate-400">{o.code}</td>
                  <td className="text-slate-200">{o.name || "—"}</td>
                  <td className={cn("font-mono", o.direction === "buy" ? "text-emerald-400" : "text-red-400")}>
                    {o.direction === "buy" ? "买" : "卖"}
                  </td>
                  <td className="text-slate-400">{o.orderType}</td>
                  <td className="text-right font-mono">{o.price > 0 ? o.price.toFixed(2) : "—"}</td>
                  <td className="text-right font-mono">{o.quantity}</td>
                  <td className="text-right font-mono text-slate-400">{o.filledQuantity}</td>
                  <td>
                    <OrderStatusBadge status={o.status} />
                  </td>
                  <td className="text-slate-500">{o.source}</td>
                  <td>
                    {canCancel ? (
                      <button
                        onClick={() => doCancel(o.id)}
                        disabled={cancelling === o.id}
                        className="text-red-400 hover:text-red-300 flex items-center gap-0.5 disabled:opacity-40"
                        title="撤单"
                      >
                        <X className="w-3.5 h-3.5" /> 撤
                      </button>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {orders.length === 0 && <div className="text-xs text-slate-600 text-center py-3">暂无订单</div>}
      </div>
    </div>
  );
}

// ============================================================
// M6 资金与收益曲线 / 统计中心
// ============================================================
function StatCard({ label, value, sub, cls }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div className="rounded border border-slate-700/50 bg-slate-800/30 px-2 py-1.5">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={cn("font-mono text-xs font-semibold", cls || "text-slate-200")}>{value}</div>
    </div>
  );
}

function StatisticsPanel({
  equity,
  stats,
  onSnapshot,
  onRefresh,
}: {
  equity: PaperEquityPoint[];
  stats: PaperAccountStatistics | null;
  onSnapshot: () => void;
  onRefresh: () => void;
}) {
  const curveData = equity.map((e) => ({ date: e.date, value: e.totalAssets }));
  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <LineChart className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">收益曲线 & 统计中心</h3>
        <button
          onClick={onSnapshot}
          className="badge badge-cyan text-[10px] cursor-pointer hover:opacity-80 flex items-center gap-1 ml-auto"
        >
          <Camera className="w-3 h-3" /> 更新快照
        </button>
        <button
          onClick={onRefresh}
          className="badge badge-gray text-[10px] cursor-pointer hover:bg-slate-700 flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" /> 刷新统计
        </button>
      </div>

      {/* 收益曲线 */}
      <div className="h-[260px]">
        {equity.length > 0 ? (
          <EquityCurveChart data={curveData} height={260} />
        ) : (
          <div className="h-full flex items-center justify-center text-slate-600 text-xs">
            暂无权益快照，点击「更新快照」生成收益曲线
          </div>
        )}
      </div>

      {/* 统计 KPI */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <StatCard
            label="累计收益率"
            value={pct(stats.cumulativePnlPct)}
            cls={getColorClass(stats.cumulativePnl)}
            sub={`年化 ${pct(stats.annualizedReturn)}`}
          />
          <StatCard label="最大回撤" value={stats.maxDrawdown.toFixed(2) + "%"} cls="text-red-400" />
          <StatCard label="夏普比率" value={stats.sharpeRatio.toFixed(2)} />
          <StatCard label="胜率" value={stats.winRate.toFixed(1) + "%"} sub={`${stats.winCount}胜 / ${stats.lossCount}负`} />
          <StatCard label="盈亏比" value={stats.profitLossRatio > 0 ? stats.profitLossRatio.toFixed(2) : "—"} />
          <StatCard label="平仓笔数" value={String(stats.tradeCount)} sub={`快照 ${stats.snapshotCount} 点`} />
          <StatCard label="累计盈亏" value={cur(stats.cumulativePnl)} cls={getColorClass(stats.cumulativePnl)} />
          <StatCard label="平均盈利" value={cur(stats.avgWin)} cls="text-emerald-400" />
          <StatCard label="平均亏损" value={cur(stats.avgLoss)} cls="text-red-400" />
        </div>
      )}
      {!stats && (
        <div className="text-xs text-slate-600 text-center">点击「刷新统计」计算绩效指标</div>
      )}
    </div>
  );
}

// ============================================================
// 主页面
// ============================================================
export default function PaperTradingPage() {
  const [accounts, setAccounts] = useState<PaperAccount[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<PaperAccountMetrics | null>(null);
  const [creating, setCreating] = useState(false);

  const [quotes, setQuotes] = useState<Record<string, PaperQuote>>({});
  const [selectedCode, setSelectedCode] = useState(WATCHLIST[0]);
  const [ob, setOb] = useState<PaperOrderBook | null>(null);
  const [kline, setKline] = useState<PaperKline | null>(null);
  const [period, setPeriod] = useState("day");
  const [sectors, setSectors] = useState<PaperSector[]>([]);
  const [sectorKind, setSectorKind] = useState<"industry" | "concept">("industry");
  const [status, setStatus] = useState<PaperMarketStatus | null>(null);
  const [live, setLive] = useState(false);

  // M3：订单 / 持仓 / 撮合状态
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [summary, setSummary] = useState<PaperPositionSummary | null>(null); // M4：持仓汇总
  const [paperBusy, setPaperBusy] = useState(false);

  // M6：收益曲线 + 统计中心
  const [equity, setEquity] = useState<PaperEquityPoint[]>([]);
  const [stats, setStats] = useState<PaperAccountStatistics | null>(null);

  // 当前选中标的的名称与现价（供下单面板使用）
  const selQuote = quotes[selectedCode];
  const selName = selQuote?.name ?? "";
  const selPrice = selQuote?.price ?? 0;

  const wsRef = useRef<WebSocket | null>(null);

  // —— 账户列表 ——
  const loadAccounts = useCallback(async () => {
    try {
      const list = await fetchPaperAccounts("demo");
      setAccounts(list);
      if (list.length > 0 && selectedId === null) {
        setSelectedId(list[0].id);
      }
    } catch (e) {
      console.error("加载模拟账户失败", e);
    }
  }, [selectedId]);

  // —— 选中账户 → 指标 ——
  const loadMetrics = useCallback(async (id: number) => {
    setMetrics(null);
    try {
      const m = await fetchPaperAccountMetrics(id);
      setMetrics(m);
    } catch (e) {
      console.error("加载账户指标失败", e);
    }
  }, []);

  // —— 选中标的 → 五档 + K线 ——
  const loadQuoteDetail = useCallback(async (code: string, pd: string) => {
    try {
      const [o, k] = await Promise.all([fetchPaperOrderBook(code), fetchPaperKline(code, pd, 120)]);
      setOb(o);
      setKline(k);
    } catch (e) {
      console.error("加载行情详情失败", e);
    }
  }, []);

  // —— 板块 ——
  const loadSectors = useCallback(async (kind: "industry" | "concept") => {
    try {
      const s = await fetchPaperSectors(kind);
      setSectors(s);
    } catch (e) {
      console.error("加载板块失败", e);
    }
  }, []);

  // —— 数据源状态 ——
  const loadStatus = useCallback(async () => {
    try {
      setStatus(await fetchPaperMarketStatus());
    } catch {
      /* ignore */
    }
  }, []);

  // —— 订单 / 持仓（M3）——
  const loadOrders = useCallback(async (id: number) => {
    try {
      setOrders(await fetchPaperOrders(id));
    } catch (e) {
      console.error("加载订单失败", e);
    }
  }, []);
  const loadPositions = useCallback(async (id: number) => {
    try {
      setPositions(await fetchPaperPositions(id));
    } catch (e) {
      console.error("加载持仓失败", e);
    }
  }, []);
  // M4：持仓汇总（盈亏/集中度/行业分布）
  const loadSummary = useCallback(async (id: number) => {
    try {
      setSummary(await fetchPaperPositionSummary(id));
    } catch (e) {
      console.error("加载持仓汇总失败", e);
    }
  }, []);
  // M6：收益曲线 + 统计中心
  const loadEquity = useCallback(async (id: number) => {
    try {
      setEquity(await fetchPaperEquity(id));
    } catch (e) {
      console.error("加载收益曲线失败", e);
    }
  }, []);
  const loadStats = useCallback(async (id: number) => {
    try {
      setStats(await fetchPaperStatistics(id));
    } catch (e) {
      console.error("加载统计失败", e);
    }
  }, []);
  // 一次刷新订单 + 持仓 + 汇总 + 统计 + 账户指标
  const reloadPaper = useCallback(
    async (id: number) => {
      await Promise.all([
        loadOrders(id), loadPositions(id), loadSummary(id),
        loadStats(id), loadEquity(id), loadMetrics(id),
      ]);
    },
    [loadOrders, loadPositions, loadSummary, loadStats, loadEquity, loadMetrics]
  );

  // 初始化
  useEffect(() => {
    loadAccounts();
    loadSectors("industry");
    loadStatus();
    loadQuoteDetail(WATCHLIST[0], "day");
    const t = setInterval(loadStatus, 30000);
    return () => clearInterval(t);
  }, [loadAccounts, loadSectors, loadStatus, loadQuoteDetail]);

  // 选中账户 → 指标
  useEffect(() => {
    if (selectedId !== null) loadMetrics(selectedId);
  }, [selectedId, loadMetrics]);

  // 选中账户 → 订单 + 持仓 + 汇总 + 收益曲线 + 统计
  useEffect(() => {
    if (selectedId !== null) {
      loadOrders(selectedId);
      loadPositions(selectedId);
      loadSummary(selectedId);
      loadEquity(selectedId);
      loadStats(selectedId);
    }
  }, [selectedId, loadOrders, loadPositions, loadSummary, loadEquity, loadStats]);

  // 选中标的 / 周期 → 详情
  useEffect(() => {
    loadQuoteDetail(selectedCode, period);
  }, [selectedCode, period, loadQuoteDetail]);

  // 板块切换
  useEffect(() => {
    loadSectors(sectorKind);
  }, [sectorKind, loadSectors]);

  // —— WebSocket 实时行情推送 ——
  useEffect(() => {
    const wsBase = API_BASE.replace(/^http/, "ws");
    let ws: WebSocket;
    try {
      ws = new WebSocket(`${wsBase}/ws/paper/market`);
    } catch {
      return;
    }
    wsRef.current = ws;
    ws.onopen = () => setLive(true);
    ws.onclose = () => setLive(false);
    ws.onerror = () => setLive(false);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "paper_market_tick" && Array.isArray(msg.quotes)) {
          setQuotes((prev) => {
            const next = { ...prev };
            for (const q of msg.quotes) next[q.code] = q;
            return next;
          });
        }
      } catch {
        /* ignore */
      }
    };
    return () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  }, []);

  const handleCreate = async (name: string, preset: string, capital: number) => {
    try {
      const acc = await createPaperAccount({
        name,
        initialCapital: capital,
        preset: preset === "custom" ? undefined : preset,
        username: "demo",
      });
      setCreating(false);
      await loadAccounts();
      setSelectedId(acc.id);
    } catch (e) {
      console.error("创建账户失败", e);
    }
  };

  // —— 撮合（手动触发，后端亦每 5s 自动重试）——
  const handleMatch = async () => {
    if (selectedId === null) return;
    setPaperBusy(true);
    try {
      await matchPaperOrders(selectedId);
      await reloadPaper(selectedId);
    } catch (e) {
      console.error("撮合失败", e);
    } finally {
      setPaperBusy(false);
    }
  };

  // —— T+1 日间清算（持仓可卖量滚动到次日）——
  const handleRollover = async () => {
    if (selectedId === null) return;
    setPaperBusy(true);
    try {
      await rolloverPaperDay(selectedId);
      await reloadPaper(selectedId);
    } catch (e) {
      console.error("清算失败", e);
    } finally {
      setPaperBusy(false);
    }
  };

  // —— 持仓市值刷新（M4）——
  const handleRefreshPositions = async () => {
    if (selectedId === null) return;
    try {
      await refreshPaperPositions(selectedId);
      await reloadPaper(selectedId);
    } catch (e) {
      console.error("刷新持仓市值失败", e);
    }
  };

  // —— M6：当日权益快照 ——
  const handleSnapshot = async () => {
    if (selectedId === null) return;
    try {
      await takePaperSnapshot(selectedId);
      await reloadPaper(selectedId);
    } catch (e) {
      console.error("权益快照失败", e);
    }
  };

  // —— M6：刷新统计（重算并写回账户绩效字段）——
  const handleRefreshStats = async () => {
    if (selectedId === null) return;
    try {
      const s = await refreshPaperStats(selectedId);
      setStats(s);
      await reloadPaper(selectedId);
    } catch (e) {
      console.error("刷新统计失败", e);
    }
  };

  // —— 撤单 ——
  const handleCancel = async (orderId: number) => {
    if (selectedId === null) return;
    try {
      await cancelPaperOrder(selectedId, orderId);
      await reloadPaper(selectedId);
    } catch (e) {
      console.error("撤单失败", e);
    }
  };

  return (
    <div className="space-y-4">
      {/* 页头 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Wallet className="w-5 h-5 text-cyan-400" /> 模拟盘交易
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            专业级 A股 模拟交易系统 · 账户 / 实时行情 / 五档 / K线 / 板块 / 下单 / 持仓 / 订单 / 收益曲线 / 统计中心 / AI 自动交易
          </p>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <span
            className={cn(
              "badge flex items-center gap-1",
              live ? "badge-live" : "badge-gray"
            )}
          >
            {live ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {live ? "WebSocket 已连接" : "WebSocket 未连接"}
          </span>
          {status && (
            <span className={cn("badge", status.mode === "real" ? "badge-green" : "badge-yellow")}>
              {status.mode === "real" ? "真实行情源" : "模拟数据源"}
            </span>
          )}
        </div>
      </div>

      {/* 网格布局 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* 左：账户 */}
        <div className="lg:col-span-3">
          <AccountPanel
            accounts={accounts}
            selectedId={selectedId}
            onSelect={setSelectedId}
            metrics={metrics}
            creating={creating}
            onStartCreate={() => setCreating((v) => !v)}
            onCreate={handleCreate}
          />
        </div>

        {/* 中：行情 + 盘口 + K线 */}
        <div className="lg:col-span-6 space-y-4">
          <WatchlistPanel quotes={quotes} selectedCode={selectedCode} onSelect={setSelectedCode} live={live} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <OrderBookPanel ob={ob} />
            <KlinePanel code={selectedCode} kline={kline} period={period} onPeriod={setPeriod} />
          </div>
        </div>

        {/* 右：板块 */}
        <div className="lg:col-span-3">
          <SectorPanel sectors={sectors} kind={sectorKind} onKind={setSectorKind} />
        </div>
      </div>

      {/* 下单 + 持仓 (M3) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4">
          <OrderPanel
            accountId={selectedId}
            code={selectedCode}
            name={selName}
            price={selPrice}
            onSubmitted={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
        <div className="lg:col-span-8">
          <PositionPanel positions={positions} summary={summary} onRefresh={handleRefreshPositions} />
        </div>
      </div>

      <CollapsibleSection title="智能风控" defaultOpen={true}>
      {/* 智能风控中心（智能风控增强） */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <RiskCenterPanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>
      </CollapsibleSection>

      <CollapsibleSection title="研究与市场">
      {/* 股票池自动维护 (M179) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <StockPoolPanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>

      {/* 研究员 Agent (#182：自动挖掘因子、生成策略) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <ResearcherAgentPanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>

      {/* 策略市场 (#183：发布/订阅/评分/排行榜) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <StrategyMarketplacePanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>
      </CollapsibleSection>

      <CollapsibleSection title="账户与复盘">
      {/* 账户总览 (#185：跨账户汇总) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <AccountOverviewPanel
            onSelectAccount={(id) => setSelectedId(id)}
          />
        </div>
      </div>

      {/* 策略组合管理 (#184：多策略统一调仓) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <PortfolioPanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>

      {/* AI 每日复盘 (#186) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <DailyReviewPanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>
      </CollapsibleSection>

      <CollapsibleSection title="交易系统 & 回测">
      {/* 订单列表 (M3) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <OrderListPanel
            orders={orders}
            onCancel={handleCancel}
            onRefresh={() => selectedId !== null && reloadPaper(selectedId)}
            onMatch={handleMatch}
            onRollover={handleRollover}
            busy={paperBusy}
          />
        </div>
      </div>

      {/* 资金与收益曲线 / 统计中心 (M6) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <StatisticsPanel
            equity={equity}
            stats={stats}
            onSnapshot={handleSnapshot}
            onRefresh={handleRefreshStats}
          />
        </div>
      </div>

      {/* AI 自动交易 (M7) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <AITradingPanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>

      {/* 回测系统 (M8) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-12">
          <BacktestPanel
            accountId={selectedId}
            onChanged={() => selectedId !== null && reloadPaper(selectedId)}
          />
        </div>
      </div>
      </CollapsibleSection>

      <div className="text-[10px] text-slate-600 flex items-center gap-1">
        <Radio className="w-3 h-3" />
        行情数据经后端 MarketProvider 统一接入（AKShare 真实源优先，外网受限时自动回退模拟数据），每个数据项自带
        dataSource 标识。撮合引擎每 5 秒自动重试挂单；回测系统 (M8) 复用主平台已验证的回测引擎（严格防未来函数，A股 T+1 友好），数据源按真实可用性诚实标注。通知中心 (M9) 等模块将在后续迭代接入。
      </div>
    </div>
  );
}
