"use client";

import { useState, useEffect } from "react";
import { PieChart, Wallet, TrendingUp, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PortfolioPosition, PortfolioAttribution } from "@/lib/api";

// ── 金额格式化 ──
function fmtMoney(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function fmtPct(v: number): string {
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

// ── 颜色 ──
const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

// ── Props ──
interface Props {
  overview: {
    totalValue: number;
    cash: number;
    positionValue: number;
    totalReturn: number;
    totalReturnAmount: number;
    todayPnl: number;
    todayPnlPct: number;
    initialCapital: number;
    positionCount: number;
  };
  positions: PortfolioPosition[];
  attribution?: PortfolioAttribution;
  loading?: boolean;
}

export function PortfolioOverview({ overview, positions, attribution, loading }: Props) {
  const [snapshots, setSnapshots] = useState<{ date: string; totalValue: number }[]>([]);
  const [activeTab, setActiveTab] = useState<"positions" | "attribution">("positions");

  // 净值迷你曲线
  const sortedPositions = [...positions].sort((a, b) => b.marketValue - a.marketValue);
  const totalMarket = positions.reduce((s, p) => s + p.marketValue, 0);

  return (
    <div className={cn("space-y-4", loading && "animate-pulse")}>
      {/* ── KPI 三宫格 ── */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
          <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1">
            <Wallet size={12} /> 总资产
          </div>
          <div className="text-lg font-mono font-bold text-white tabular-nums">
            ¥{fmtMoney(overview.totalValue)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            初始 ¥{fmtMoney(overview.initialCapital)}
          </div>
        </div>
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
          <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1">
            <TrendingUp size={12} /> 累计收益
          </div>
          <div className={cn(
            "text-lg font-mono font-bold tabular-nums",
            overview.totalReturn >= 0 ? "text-emerald-400" : "text-red-400",
          )}>
            {fmtPct(overview.totalReturn)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            ¥{fmtMoney(overview.totalReturnAmount)}
          </div>
        </div>
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
          <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1">
            <PieChart size={12} /> 持仓
          </div>
          <div className="text-lg font-mono font-bold text-white tabular-nums">
            {overview.positionCount} 只
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            仓位 ¥{fmtMoney(overview.positionValue)} / ¥{fmtMoney(overview.cash)} 现金
          </div>
        </div>
      </div>

      {/* ── 日内盈亏 ── */}
      <div className={cn(
        "rounded-lg border p-3",
        overview.todayPnl >= 0
          ? "border-emerald-700/30 bg-emerald-950/20"
          : "border-red-700/30 bg-red-950/20",
      )}>
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-slate-400">今日盈亏</span>
          <div className="flex items-center gap-1.5">
            {overview.todayPnl >= 0 ? (
              <ArrowUpRight size={14} className="text-emerald-400" />
            ) : (
              <ArrowDownRight size={14} className="text-red-400" />
            )}
            <span className={cn(
              "text-sm font-mono font-bold tabular-nums",
              overview.todayPnl >= 0 ? "text-emerald-400" : "text-red-400",
            )}>
              ¥{fmtMoney(overview.todayPnl)} ({fmtPct(overview.todayPnlPct)})
            </span>
          </div>
        </div>
      </div>

      {/* ── Tab 切换 ── */}
      <div className="flex gap-1 border-b border-slate-700/50">
        <button
          onClick={() => setActiveTab("positions")}
          className={cn(
            "px-3 py-1.5 text-[11px] font-medium border-b-2 transition-colors",
            activeTab === "positions"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-slate-500 hover:text-slate-300",
          )}
        >
          持仓明细
        </button>
        <button
          onClick={() => setActiveTab("attribution")}
          className={cn(
            "px-3 py-1.5 text-[11px] font-medium border-b-2 transition-colors",
            activeTab === "attribution"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-slate-500 hover:text-slate-300",
          )}
        >
          Brinson 归因
        </button>
      </div>

      {/* ── 持仓明细 ── */}
      {activeTab === "positions" && (
        <div className="space-y-2">
          {/* 饼图替代：权重条 */}
          {sortedPositions.length > 0 && (
            <div className="flex h-2 rounded-full overflow-hidden bg-slate-700/50">
              {sortedPositions.map((p, i) => (
                <div
                  key={p.code}
                  className="h-full transition-all"
                  style={{
                    width: `${p.weight}%`,
                    backgroundColor: COLORS[i % COLORS.length],
                  }}
                  title={`${p.name} ${p.weight}%`}
                />
              ))}
            </div>
          )}
          {/* 持仓表 */}
          <div className="rounded-lg border border-slate-700/50 overflow-hidden">
            <table className="w-full text-[11px]">
              <thead className="bg-slate-800/80 text-slate-400">
                <tr>
                  <th className="text-left py-2 px-3 font-medium">名称</th>
                  <th className="text-right py-2 px-2 font-medium">持仓</th>
                  <th className="text-right py-2 px-2 font-medium">成本</th>
                  <th className="text-right py-2 px-2 font-medium">现价</th>
                  <th className="text-right py-2 px-2 font-medium">市值</th>
                  <th className="text-right py-2 px-2 font-medium">权重</th>
                  <th className="text-right py-2 px-3 font-medium">盈亏</th>
                </tr>
              </thead>
              <tbody>
                {sortedPositions.map((p, i) => (
                  <tr key={p.code} className={cn(
                    "border-t border-slate-700/30",
                    i % 2 === 0 ? "bg-slate-800/20" : "",
                  )}>
                    <td className="py-2 px-3">
                      <div className="text-white font-medium">{p.name}</div>
                      <div className="text-[10px] text-slate-500">{p.code}</div>
                    </td>
                    <td className="py-2 px-2 text-right text-white tabular-nums">{p.shares}</td>
                    <td className="py-2 px-2 text-right text-slate-300 tabular-nums">¥{p.avgCost.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right text-slate-300 tabular-nums">¥{p.currentPrice.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right text-white tabular-nums">¥{fmtMoney(p.marketValue)}</td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono"
                        style={{ backgroundColor: COLORS[i % COLORS.length] + "30", color: COLORS[i % COLORS.length] }}>
                        {p.weight}%
                      </span>
                    </td>
                    <td className={cn(
                      "py-2 px-3 text-right font-mono tabular-nums",
                      p.unrealizedPnlPct >= 0 ? "text-emerald-400" : "text-red-400",
                    )}>
                      {fmtPct(p.unrealizedPnlPct)}
                    </td>
                  </tr>
                ))}
                {sortedPositions.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-slate-500 text-xs">
                      暂无持仓，请先下单
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Brinson 归因 ── */}
      {activeTab === "attribution" && (
        <div className="space-y-3">
          {attribution ? (
            <>
              {/* 归因摘要 */}
              <div className="grid grid-cols-4 gap-2">
                <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-2 text-center">
                  <div className="text-[10px] text-slate-400">组合收益</div>
                  <div className={cn("text-sm font-mono font-bold", attribution.portfolioReturn >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {fmtPct(attribution.portfolioReturn)}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-2 text-center">
                  <div className="text-[10px] text-slate-400">基准收益</div>
                  <div className="text-sm font-mono font-bold text-white">
                    {fmtPct(attribution.benchmarkReturn)}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-2 text-center">
                  <div className="text-[10px] text-slate-400">超额收益</div>
                  <div className={cn("text-sm font-mono font-bold", attribution.excessReturn >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {fmtPct(attribution.excessReturn)}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-2 text-center">
                  <div className="text-[10px] text-slate-400">归因方法</div>
                  <div className="text-xs text-slate-300 mt-0.5">Brinson</div>
                </div>
              </div>
              {/* 三效应分解 */}
              <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
                <div className="text-[10px] text-slate-400 mb-2">收益分解</div>
                <div className="space-y-1.5">
                  {[
                    { label: "配置效应", value: attribution.allocation, color: "text-blue-400" },
                    { label: "选股效应", value: attribution.selection, color: "text-purple-400" },
                    { label: "交互效应", value: attribution.interaction, color: "text-amber-400" },
                  ].map((e) => (
                    <div key={e.label} className="flex items-center justify-between text-xs">
                      <span className="text-slate-400">{e.label}</span>
                      <div className="flex items-center gap-2">
                        <span className={cn("font-mono font-bold", e.color)}>
                          {e.value >= 0 ? "+" : ""}{e.value.toFixed(3)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {/* 个股归因 */}
              {attribution.breakdown.length > 0 && (
                <div className="rounded-lg border border-slate-700/50 overflow-hidden">
                  <table className="w-full text-[10px]">
                    <thead className="bg-slate-800/80 text-slate-400">
                      <tr>
                        <th className="py-1.5 px-2 text-left">个股</th>
                        <th className="py-1.5 px-1 text-right">行业</th>
                        <th className="py-1.5 px-1 text-right">权重(P/B)</th>
                        <th className="py-1.5 px-1 text-right">收益</th>
                        <th className="py-1.5 px-1 text-right">配置</th>
                        <th className="py-1.5 px-1 text-right">选股</th>
                        <th className="py-1.5 px-1 text-right">交互</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attribution.breakdown.map((b, i) => (
                        <tr key={b.code} className={cn("border-t border-slate-700/30", i % 2 === 0 ? "bg-slate-800/20" : "")}>
                          <td className="py-1.5 px-2 text-white font-medium">{b.name}</td>
                          <td className="py-1.5 px-1 text-right text-slate-500">{b.industry}</td>
                          <td className="py-1.5 px-1 text-right font-mono text-slate-300">
                            {b.portfolioWeight}%/{b.benchmarkWeight}%
                          </td>
                          <td className={cn("py-1.5 px-1 text-right font-mono", b.stockReturn >= 0 ? "text-emerald-400" : "text-red-400")}>
                            {fmtPct(b.stockReturn)}
                          </td>
                          <td className={cn("py-1.5 px-1 text-right font-mono", b.allocationEffect >= 0 ? "text-blue-400" : "text-red-400")}>
                            {b.allocationEffect >= 0 ? "+" : ""}{b.allocationEffect.toFixed(2)}
                          </td>
                          <td className={cn("py-1.5 px-1 text-right font-mono", b.selectionEffect >= 0 ? "text-purple-400" : "text-red-400")}>
                            {b.selectionEffect >= 0 ? "+" : ""}{b.selectionEffect.toFixed(2)}
                          </td>
                          <td className={cn("py-1.5 px-1 text-right font-mono", b.interactionEffect >= 0 ? "text-amber-400" : "text-red-400")}>
                            {b.interactionEffect >= 0 ? "+" : ""}{b.interactionEffect.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <div className="py-6 text-center text-slate-500 text-xs">
              暂无归因数据
            </div>
          )}
        </div>
      )}
    </div>
  );
}
