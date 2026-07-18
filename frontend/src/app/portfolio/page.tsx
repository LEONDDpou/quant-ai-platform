"use client";

import { useState, useEffect, useCallback } from "react";
import {
  RefreshCw, TrendingUp, Shield, ArrowUpDown, PieChart,
  AlertTriangle, ArrowUpRight, ArrowDownRight, Wallet,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getPortfolioOverview, getPortfolioPositions, getPortfolioAttribution,
  getPortfolioRisk, getRebalanceAdvice, getPortfolioOrders, getPortfolioSnapshots,
  type PortfolioOverview as TOverview, type PortfolioPosition,
  type PortfolioAttribution, type PortfolioRisk,
  type RebalanceAdvice, type PortfolioOrder, type SnapshotEntry,
} from "@/lib/api";
import { PortfolioOverview as OverviewPanel } from "@/components/ui/PortfolioOverview";

// ── 金额格式化 ──
function fmtMoney(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function fmtPct(v: number): string {
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

// ── Tab 定义 ──
type TabId = "overview" | "attribution" | "risk" | "rebalance";

// ── 风险仪表盘迷你组件 ──
function RiskGauge({ label, value, unit, warn, danger, invert }: {
  label: string; value: number; unit: string; warn: number; danger: number; invert?: boolean;
}) {
  const isGood = invert ? value <= warn : value >= (1 - warn);
  const isBad = invert ? value >= danger : value <= (1 - danger);
  const color = isGood ? "text-emerald-400" : isBad ? "text-red-400" : "text-amber-400";

  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3 text-center">
      <div className="text-[10px] text-slate-400 mb-1">{label}</div>
      <div className={cn("text-lg font-mono font-bold", color)}>
        {value.toFixed(2)}{unit}
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [loading, setLoading] = useState(true);

  const [overview, setOverview] = useState<TOverview | null>(null);
  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [attribution, setAttribution] = useState<PortfolioAttribution | null>(null);
  const [risk, setRisk] = useState<PortfolioRisk | null>(null);
  const [rebalance, setRebalance] = useState<RebalanceAdvice | null>(null);
  const [orders, setOrders] = useState<PortfolioOrder[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotEntry[]>([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, pos, attr, rsk, reb, ord, snap] = await Promise.all([
        getPortfolioOverview(),
        getPortfolioPositions(),
        getPortfolioAttribution(),
        getPortfolioRisk(),
        getRebalanceAdvice(),
        getPortfolioOrders(30),
        getPortfolioSnapshots(30),
      ]);
      setOverview(ov);
      setPositions(pos);
      setAttribution(attr);
      setRisk(rsk);
      setRebalance(reb);
      setOrders(ord);
      setSnapshots(snap);
    } catch (e) {
      console.error("Portfolio fetch error:", e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const tabs: { id: TabId; icon: React.ReactNode; label: string }[] = [
    { id: "overview", icon: <PieChart size={14} />, label: "持仓概览" },
    { id: "attribution", icon: <ArrowUpDown size={14} />, label: "收益归因" },
    { id: "risk", icon: <Shield size={14} />, label: "风险指标" },
    { id: "rebalance", icon: <RefreshCw size={14} />, label: "再平衡" },
  ];

  return (
    <div className="h-full overflow-auto bg-[#0b0f19]">
      <div className="max-w-7xl mx-auto p-4 space-y-4">
        {/* 顶栏 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-bold text-white">组合管理</h1>
            <p className="text-[11px] text-slate-500">Portfolio Management — 模拟账户 · 归因 · 风险</p>
          </div>
          <button
            onClick={fetchAll}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            <RefreshCw size={12} className={cn(loading && "animate-spin")} />
            刷新
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-700/50">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 text-[12px] font-medium border-b-2 transition-colors",
                activeTab === t.id
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-slate-500 hover:text-slate-300",
              )}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* ── Tab 1: 持仓概览 ── */}
        {activeTab === "overview" && overview && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <OverviewPanel
                overview={overview}
                positions={positions}
                attribution={attribution ?? undefined}
                loading={loading}
              />
            </div>
            {/* 右侧：历史净值 + 订单 */}
            <div className="space-y-4">
              {/* 净值曲线 SVG */}
              <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
                <div className="text-[11px] text-slate-400 mb-2">净值走势（30日快照）</div>
                {snapshots.length > 1 ? (
                  <svg viewBox={`0 0 280 100`} className="w-full h-24">
                    <defs>
                      <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    {(() => {
                      const vals = snapshots.map(s => s.totalValue);
                      const min = Math.min(...vals) * 0.995;
                      const max = Math.max(...vals) * 1.005;
                      const range = max - min || 1;
                      const pts = vals.map((v, i) =>
                        `${(i / (vals.length - 1)) * 280},${100 - ((v - min) / range) * 90 - 5}`
                      );
                      return (
                        <>
                          <polygon
                            points={`0,100 ${pts.join(" ")} 280,100`}
                            fill="url(#areaGrad)"
                          />
                          <polyline
                            points={pts.join(" ")}
                            fill="none"
                            stroke="#3b82f6"
                            strokeWidth="1.5"
                          />
                        </>
                      );
                    })()}
                  </svg>
                ) : (
                  <div className="h-24 flex items-center justify-center text-xs text-slate-600">
                    暂无足够快照数据
                  </div>
                )}
              </div>

              {/* 最近订单 */}
              <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
                <div className="text-[11px] text-slate-400 mb-2">最近成交</div>
                <div className="space-y-1.5 max-h-64 overflow-auto">
                  {orders.filter(o => o.status === "filled").slice(0, 8).map(o => (
                    <div key={o.id} className="flex items-center justify-between text-[10px]">
                      <div className="flex items-center gap-1.5">
                        <span className={cn(
                          "px-1 rounded text-[9px] font-medium",
                          o.direction === "buy"
                            ? "bg-emerald-950/50 text-emerald-400"
                            : "bg-red-950/50 text-red-400"
                        )}>
                          {o.direction === "buy" ? "买入" : "卖出"}
                        </span>
                        <span className="text-slate-300">{o.name}</span>
                        <span className="text-slate-500">{o.shares}股</span>
                      </div>
                      <span className="text-slate-400 font-mono">¥{o.price.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Tab 2: 收益归因 ── */}
        {activeTab === "attribution" && attribution && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                { label: "组合收益", value: attribution.portfolioReturn, color: "emerald" },
                { label: "基准收益", value: attribution.benchmarkReturn, color: "white" },
                { label: "超额收益", value: attribution.excessReturn, color: "blue" },
                { label: "配置效应", value: attribution.allocation, color: "purple" },
              ].map(e => (
                <div key={e.label} className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3 text-center">
                  <div className="text-[10px] text-slate-400">{e.label}</div>
                  <div className={cn("text-base font-mono font-bold mt-1", {
                    "text-emerald-400": e.color === "emerald",
                    "text-white": e.color === "white",
                    "text-blue-400": e.color === "blue",
                    "text-purple-400": e.color === "purple",
                  })}>
                    {e.value >= 0 ? "+" : ""}{e.value.toFixed(3)}%
                  </div>
                </div>
              ))}
            </div>
            {/* 详细归因表 */}
            <div className="rounded-lg border border-slate-700/50 overflow-hidden">
              <table className="w-full text-[11px]">
                <thead className="bg-slate-800/80 text-slate-400">
                  <tr>
                    <th className="py-2 px-3 text-left">个股</th>
                    <th className="py-2 px-2 text-left">行业</th>
                    <th className="py-2 px-2 text-right">组合权重</th>
                    <th className="py-2 px-2 text-right">基准权重</th>
                    <th className="py-2 px-2 text-right">个股收益</th>
                    <th className="py-2 px-2 text-right">行业收益</th>
                    <th className="py-2 px-2 text-right">配置效应</th>
                    <th className="py-2 px-2 text-right">选股效应</th>
                    <th className="py-2 px-2 text-right">交互效应</th>
                  </tr>
                </thead>
                <tbody>
                  {attribution.breakdown.map((b, i) => (
                    <tr key={b.code} className={cn("border-t border-slate-700/30", i % 2 === 0 ? "bg-slate-800/20" : "")}>
                      <td className="py-2 px-3 text-white font-medium">{b.name}</td>
                      <td className="py-2 px-2 text-slate-500">{b.industry}</td>
                      <td className="py-2 px-2 text-right text-slate-300">{b.portfolioWeight}%</td>
                      <td className="py-2 px-2 text-right text-slate-500">{b.benchmarkWeight}%</td>
                      <td className={cn("py-2 px-2 text-right font-mono", b.stockReturn >= 0 ? "text-emerald-400" : "text-red-400")}>
                        {fmtPct(b.stockReturn)}
                      </td>
                      <td className={cn("py-2 px-2 text-right font-mono", b.industryReturn >= 0 ? "text-slate-300" : "text-red-400")}>
                        {fmtPct(b.industryReturn)}
                      </td>
                      <td className={cn("py-2 px-2 text-right font-mono", b.allocationEffect >= 0 ? "text-blue-400" : "text-red-400")}>
                        {b.allocationEffect >= 0 ? "+" : ""}{b.allocationEffect.toFixed(2)}
                      </td>
                      <td className={cn("py-2 px-2 text-right font-mono", b.selectionEffect >= 0 ? "text-purple-400" : "text-red-400")}>
                        {b.selectionEffect >= 0 ? "+" : ""}{b.selectionEffect.toFixed(2)}
                      </td>
                      <td className={cn("py-2 px-2 text-right font-mono", b.interactionEffect >= 0 ? "text-amber-400" : "text-red-400")}>
                        {b.interactionEffect >= 0 ? "+" : ""}{b.interactionEffect.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Tab 3: 风险指标 ── */}
        {activeTab === "risk" && risk && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
              <RiskGauge label="VaR (95%)" value={risk.var95} unit="%" warn={0.05} danger={0.1} />
              <RiskGauge label="CVaR (95%)" value={risk.cvar95} unit="%" warn={0.07} danger={0.15} />
              <RiskGauge label="VaR (99%)" value={risk.var99} unit="%" warn={0.08} danger={0.18} />
              <RiskGauge label="年化波动率" value={risk.annualVolatility} unit="%" warn={0.25} danger={0.4} />
              <RiskGauge label="夏普比率" value={risk.sharpeRatio} unit="" warn={0.5} danger={0} invert />
              <RiskGauge label="最大回撤" value={risk.maxDrawdown} unit="%" warn={0.15} danger={0.3} />
            </div>
            <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
              <div className="text-[11px] text-slate-400">
                计算方法：{risk.method} · 置信水平：{risk.confidence}
              </div>
            </div>
            <div className="rounded-lg border border-slate-700/50 bg-amber-950/20 border-amber-700/30 p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle size={14} className="text-amber-400 mt-0.5 shrink-0" />
                <div className="text-[11px] text-amber-300">
                  <p className="font-medium mb-1">风险解读</p>
                  <ul className="list-disc pl-4 space-y-0.5 text-[10px] text-amber-300/70">
                    <li>VaR95={risk.var95}%：95%置信度下，组合单日最大损失不超过 {risk.var95}%</li>
                    <li>CVaR95={risk.cvar95}%：尾部极端情况下的平均损失约为 {risk.cvar95}%</li>
                    <li>{risk.maxDrawdown > 20 ? "⚠️ 当前最大回撤超过20%，需要关注风控" : "最大回撤在可控范围内"}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Tab 4: 再平衡 ── */}
        {activeTab === "rebalance" && rebalance && (
          <div className="space-y-4">
            <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
              <div className="text-sm font-bold text-white mb-1">再平衡建议</div>
              <div className="text-[11px] text-slate-400">{rebalance.summary}</div>
            </div>
            {/* 当前行业权重 vs 目标 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
                <div className="text-[11px] text-slate-400 mb-2">当前行业配置</div>
                {Object.entries(rebalance.currentIndustryWeights).map(([ind, w]) => (
                  <div key={ind} className="flex items-center justify-between text-[11px] py-1 border-b border-slate-700/30 last:border-0">
                    <span className="text-slate-300">{ind}</span>
                    <span className="font-mono text-white">{w}%</span>
                  </div>
                ))}
              </div>
              <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
                <div className="text-[11px] text-slate-400 mb-2">目标行业配置</div>
                {Object.entries(rebalance.targetWeights).map(([ind, w]) => (
                  <div key={ind} className="flex items-center justify-between text-[11px] py-1 border-b border-slate-700/30 last:border-0">
                    <span className="text-slate-300">{ind}</span>
                    <span className="font-mono text-blue-400">{w}%</span>
                  </div>
                ))}
              </div>
            </div>
            {/* 调仓方案 */}
            {rebalance.advice.length > 0 && (
              <div className="rounded-lg border border-slate-700/50 overflow-hidden">
                <table className="w-full text-[11px]">
                  <thead className="bg-slate-800/80 text-slate-400">
                    <tr>
                      <th className="py-2 px-3 text-left">行业</th>
                      <th className="py-2 px-2 text-right">当前权重</th>
                      <th className="py-2 px-2 text-right">目标权重</th>
                      <th className="py-2 px-2 text-right">偏离度</th>
                      <th className="py-2 px-2 text-right">调仓金额</th>
                      <th className="py-2 px-3 text-center">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rebalance.advice.map((a, i) => (
                      <tr key={a.industry} className={cn(
                        "border-t border-slate-700/30",
                        i % 2 === 0 ? "bg-slate-800/20" : "",
                      )}>
                        <td className="py-2 px-3 text-white font-medium">{a.industry}</td>
                        <td className="py-2 px-2 text-right text-slate-300">{a.currentWeight}%</td>
                        <td className="py-2 px-2 text-right text-blue-400">{a.targetWeight}%</td>
                        <td className={cn(
                          "py-2 px-2 text-right font-mono",
                          Math.abs(a.drift) > 8 ? "text-red-400" : "text-amber-400",
                        )}>
                          {a.drift >= 0 ? "+" : ""}{a.drift}%
                        </td>
                        <td className="py-2 px-2 text-right font-mono text-white">
                          ¥{fmtMoney(a.adjustAmount)}
                        </td>
                        <td className="py-2 px-3 text-center">
                          <span className={cn(
                            "px-1.5 py-0.5 rounded text-[10px] font-medium",
                            a.action === "增配"
                              ? "bg-emerald-950/50 text-emerald-400"
                              : "bg-red-950/50 text-red-400",
                          )}>
                            {a.action}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* 加载中 */}
        {loading && !overview && (
          <div className="py-20 text-center">
            <RefreshCw size={24} className="animate-spin text-slate-600 mx-auto mb-3" />
            <div className="text-xs text-slate-500">加载组合数据...</div>
          </div>
        )}
      </div>
    </div>
  );
}
