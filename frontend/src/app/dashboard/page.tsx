"use client";

import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  Thermometer, Brain, CandlestickChart, ArrowDownToLine,
  ShieldAlert, Briefcase, RefreshCw, TrendingUp, TrendingDown,
  AlertTriangle, Info, Zap, Star, ChevronRight, CircleDollarSign,
} from "lucide-react";
import dynamic from "next/dynamic";
import type { EChartsOption } from "echarts";
// ECharts 体积大（数百 KB~1MB），改为按需动态加载，移出首屏关键路径，避免阻塞 TTI
const ReactECharts = dynamic(() => import("echarts-for-react"), {
  ssr: false,
  loading: () => <div className="h-full w-full" />,
});
import { cn } from "@/lib/utils";
import { fetchDashboardV2, type DashboardV2Data, type KlineBar } from "@/lib/api";
import { LiveMarketBar } from "@/components/LiveMarketBar";

// ============================================================
// Helpers
// ============================================================
const FMT = (n: number, d = 2) => n.toLocaleString("zh-CN", { minimumFractionDigits: d, maximumFractionDigits: d });
const PCT = (n: number) => (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
const RISK_COLORS: Record<string, string> = { low: "#34d399", medium: "#fbbf24", high: "#f97316", extreme: "#ef4444" };
const SEVERITY_BADGE: Record<string, string> = {
  info: "badge-blue", warning: "badge-yellow", critical: "badge-red",
};
const SEVERITY_ICON: Record<string, typeof AlertTriangle> = {
  info: Info, warning: AlertTriangle, critical: AlertTriangle,
};
const TREND_MAP: Record<string, string> = {
  "强势": "badge-bullish", "震荡偏强": "badge-bullish", "震荡": "badge-neutral",
  "震荡偏弱": "badge-bearish", "弱势": "badge-bearish",
};

// ============================================================
// Screen 1 — 市场概览
// ============================================================
function ScreenMarketOverview({ data }: { data: DashboardV2Data }) {
  const { indices, temperature } = data;
  const t = temperature;
  const scoreColor = t.score >= 70 ? "#ef4444" : t.score >= 50 ? "#fbbf24" : t.score >= 30 ? "#3b82f6" : "#34d399";

  return (
    <div className="card p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <Thermometer className="w-4 h-4 text-orange-400" />
        <h3 className="section-title">市场概览</h3>
        <span className="badge badge-green text-[10px] ml-auto">
          {data._meta.westockAvailable ? "实时" : "缓存"}
        </span>
      </div>

      {/* WebSocket 实时行情订阅条（共享快照缓存，后端只拉一次全量） */}
      <div className="mb-3 pb-3 border-b border-white/5">
        <LiveMarketBar />
      </div>

      {/* 温度计弧形仪表 + 四维度 */}
      <div className="flex items-center gap-4 mb-3">
        <div className="relative w-20 h-20 shrink-0">
          <svg viewBox="0 0 100 60" className="w-full h-full -rotate-90">
            <defs>
              <linearGradient id="tempGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#34d399" />
                <stop offset="40%" stopColor="#3b82f6" />
                <stop offset="70%" stopColor="#fbbf24" />
                <stop offset="100%" stopColor="#ef4444" />
              </linearGradient>
            </defs>
            {/* Background arc */}
            <path d="M10 50 A40 40 0 0 1 90 50" fill="none" stroke="#151d2e" strokeWidth="8" strokeLinecap="round" />
            {/* Value arc */}
            <path d="M10 50 A40 40 0 0 1 90 50" fill="none" stroke="url(#tempGrad)" strokeWidth="8"
              strokeLinecap="round" strokeDasharray={`${t.score * 1.256} 126`} />
            {/* Needle */}
            <line x1="50" y1="52" x2={50 + 40 * Math.cos(Math.PI - (t.score / 100) * Math.PI)}
              y2={50 - 40 * Math.sin(Math.PI - (t.score / 100) * Math.PI)}
              stroke="#e8edf5" strokeWidth="2" strokeLinecap="round" />
            <circle cx="50" cy="50" r="3" fill="#e8edf5" />
          </svg>
        </div>
        <div>
          <div className="text-2xl font-bold" style={{ color: scoreColor }}>{t.score.toFixed(0)}</div>
          <div className="text-xs" style={{ color: scoreColor }}>{t.riskLabel}</div>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 ml-auto text-[10px]">
          {(["valuation", "sentiment", "capital", "technical"] as const).map((dim) => (
            <div key={dim} className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: RISK_COLORS[t[dim].score >= 65 ? "high" : t[dim].score >= 45 ? "medium" : "low"] }} />
              <span className="text-slate-500">{{ valuation: "估值", sentiment: "情绪", capital: "资金", technical: "技术" }[dim]}</span>
              <span className="text-slate-400 font-mono">{t[dim].score.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 指数迷你卡片 */}
      <div className="grid grid-cols-5 gap-2 mb-0 flex-1 content-start">
        {indices.map((idx) => (
          <div key={idx.code} className="bg-[#0b1120] rounded-lg p-2 border border-[#151d2e] text-center">
            <div className="text-[10px] text-slate-500 truncate">{idx.name}</div>
            <div className="text-xs font-mono font-bold text-slate-200 mt-0.5">{idx.value.toFixed(0)}</div>
            <div className={cn("text-[10px] font-mono mt-0.5", idx.changePct >= 0 ? "text-emerald-400" : "text-red-400")}>
              {PCT(idx.changePct)}
            </div>
            {/* Mini sparkline */}
            {idx.sparkline?.length > 0 && (
              <div className="mt-1 h-5">
                <svg viewBox={`0 0 ${idx.sparkline.length} 20`} className="w-full h-full" preserveAspectRatio="none">
                  <polyline
                    fill="none"
                    stroke={idx.changePct >= 0 ? "#34d399" : "#f87171"}
                    strokeWidth="1"
                    points={idx.sparkline.map((v, i, a) => {
                      const max = Math.max(...a), min = Math.min(...a), r = max - min || 1;
                      return `${i},${19 - ((v - min) / r) * 17}`;
                    }).join(" ")}
                  />
                </svg>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// Screen 2 — AI 市场研判
// ============================================================
function ScreenAIJudgment({ data }: { data: DashboardV2Data }) {
  const j = data.judgment;
  if (!j || !j.marketTrend) {
    return (
      <div className="card p-4 h-full flex items-center justify-center text-slate-600 text-xs">
        <RefreshCw className="w-4 h-4 animate-spin mr-2" /> AI 研判生成中...
      </div>
    );
  }

  const RiskIcon = j.riskStars >= 4 ? AlertTriangle : j.riskStars >= 3 ? ShieldAlert : ShieldAlert;
  const riskColor = j.riskStars >= 4 ? "text-red-400" : j.riskStars >= 3 ? "text-amber-400" : "text-emerald-400";

  return (
    <div className="card p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-purple-400" />
        <h3 className="section-title">AI 市场研判</h3>
        <span className="badge badge-purple text-[10px] ml-auto">{j.generatedBy || "AI"}</span>
      </div>

      {/* 大盘判断 + 风险星级 + AI评分 */}
      <div className="flex items-center gap-3 mb-3 p-3 bg-[#0b1120] rounded-lg border border-[#151d2e]">
        <span className={cn("badge text-xs px-2 py-0.5", TREND_MAP[j.marketTrend] || "badge-neutral")}>{j.marketTrend}</span>
        <div className="flex items-center gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star key={i} className={cn("w-3.5 h-3.5", i < j.riskStars ? riskColor : "text-slate-700")} fill={i < j.riskStars ? "currentColor" : "none"} />
          ))}
        </div>
        <span className="text-xs text-slate-400 ml-auto">
          AI 评分 <span className={cn("font-bold", j.aiScore >= 60 ? "text-emerald-400" : j.aiScore >= 40 ? "text-amber-400" : "text-red-400")}>{j.aiScore}</span>
        </span>
      </div>

      {/* Summary */}
      <p className="text-xs text-slate-400 leading-relaxed mb-3 line-clamp-2">{j.marketSummary}</p>

      {/* Strong / Weak sectors */}
      <div className="grid grid-cols-2 gap-3 mb-2 flex-1">
        <div>
          <div className="text-[10px] text-emerald-400/70 mb-1">📈 强势板块</div>
          <div className="flex flex-wrap gap-1">
            {(j.strongSectors || []).slice(0, 4).map((s) => (
              <span key={s} className="badge badge-green text-[9px]">{s}</span>
            ))}
            {(!j.strongSectors || j.strongSectors.length === 0) && <span className="text-[10px] text-slate-600">—</span>}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-red-400/70 mb-1">📉 弱势板块</div>
          <div className="flex flex-wrap gap-1">
            {(j.weakSectors || []).slice(0, 4).map((s) => (
              <span key={s} className="badge badge-red text-[9px]">{s}</span>
            ))}
            {(!j.weakSectors || j.weakSectors.length === 0) && <span className="text-[10px] text-slate-600">—</span>}
          </div>
        </div>
      </div>

      {/* 热点主题 */}
      {(j.hotThemes || []).length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] text-purple-400/70 mb-1">🔥 热点题材</div>
          <div className="flex flex-wrap gap-1">
            {j.hotThemes.slice(0, 5).map((t) => (
              <span key={t} className="badge badge-purple text-[9px]">{t}</span>
            ))}
          </div>
        </div>
      )}

      {/* 操作建议 */}
      <div className="bg-amber-500/5 rounded-lg p-2 border border-amber-500/10">
        <div className="flex items-center gap-1 mb-1">
          <Zap className="w-3 h-3 text-amber-400" />
          <span className="text-[10px] text-amber-400 font-medium">仓位建议</span>
        </div>
        <p className="text-[11px] text-slate-300 leading-relaxed">{j.positionAdvice}</p>
      </div>
    </div>
  );
}

// ============================================================
// Screen 3 — K 线 + 策略信号
// ============================================================
function ScreenKlineSignals({ data }: { data: DashboardV2Data }) {
  const { klineSignals } = data;
  const watchlist = klineSignals?.watchlist || [];
  const klineData = klineSignals?.klineData || {};
  const [activeCode, setActiveCode] = useState(watchlist[0] || "");
  const [period, setPeriod] = useState("1D");

  // ECharts candlestick
  const klineOption: EChartsOption = useMemo(() => {
    const bars = klineData[activeCode] || [];
    if (bars.length === 0) return {};
    const dates = bars.map((b: KlineBar) => b.date.slice(5)); // MM-DD
    const ohlc = bars.map((b: KlineBar) => [b.open, b.close, b.low, b.high]);
    const volumes = bars.map((b: KlineBar) => b.volume);
    const upColor = "#34d399"; const downColor = "#f87171";

    return {
      backgroundColor: "transparent",
      grid: [{ top: 15, right: 60, bottom: 70, left: 50 }, { top: 235, right: 60, bottom: 15, left: 50 }],
      tooltip: { trigger: "axis", backgroundColor: "#0f172a", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 10 } },
      xAxis: [
        { type: "category", data: dates, axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 9, interval: Math.max(1, Math.floor(dates.length / 6)) } },
        { type: "category", gridIndex: 1, data: dates, axisLabel: { show: false } },
      ],
      yAxis: [
        { type: "value", scale: true, axisLine: { show: false }, splitLine: { lineStyle: { color: "#10172a" } }, axisLabel: { color: "#5a6a82", fontSize: 9 } },
        { type: "value", gridIndex: 1, axisLine: { show: false }, splitLine: { show: false }, axisLabel: { color: "#5a6a82", fontSize: 9 } },
      ],
      series: [
        { type: "candlestick", data: ohlc, itemStyle: { color: upColor, color0: downColor, borderColor: upColor, borderColor0: downColor } },
        { type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: volumes, itemStyle: { color: (p: { dataIndex: number }) => {
          const bar = ohlc[p.dataIndex]; return bar ? (bar[1] >= bar[0] ? "rgba(52,211,153,0.3)" : "rgba(248,113,113,0.3)") : "rgba(100,116,139,0.3)";
        } } },
      ],
    };
  }, [activeCode, klineData]);

  const latestBar = (klineData[activeCode] || []).slice(-1)[0] as KlineBar | undefined;
  const prevBar = (klineData[activeCode] || []).slice(-2, -1)[0] as KlineBar | undefined;
  const price = latestBar?.close ?? 0;
  const pct = prevBar ? ((price - prevBar.close) / prevBar.close * 100) : 0;

  return (
    <div className="card p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <CandlestickChart className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">K线信号</h3>
        {/* Period switcher */}
        <div className="flex gap-0.5 ml-auto">
          {["1D", "1W"].map((p) => (
            <button key={p} onClick={() => setPeriod(p)} className={cn(
              "px-2 py-0.5 text-[10px] rounded", period === p ? "bg-[#1e293b] text-cyan-400" : "text-slate-600 hover:text-slate-400"
            )}>{p}</button>
          ))}
        </div>
      </div>

      {/* Stock switcher + Price */}
      <div className="flex items-center gap-2 mb-1">
        {watchlist.map((code) => (
          <button key={code} onClick={() => setActiveCode(code)} className={cn(
            "px-2 py-0.5 text-[10px] font-mono rounded transition-colors",
            activeCode === code ? "bg-[#1e293b] text-cyan-400" : "text-slate-600 hover:text-slate-400"
          )}>{code.replace(/\.(SH|SZ)$/, "")}</button>
        ))}
        {price > 0 && (
          <span className="ml-auto text-sm font-mono text-slate-200">
            ¥{price.toFixed(2)} <span className={cn("text-xs", pct >= 0 ? "text-emerald-400" : "text-red-400")}>{PCT(pct)}</span>
          </span>
        )}
      </div>

      {/* K-line chart */}
      <div className="flex-1 min-h-0">
        {Object.keys(klineData).length > 0 ? (
          <ReactECharts option={klineOption} style={{ height: "100%", width: "100%" }} />
        ) : (
          <div className="flex items-center justify-center h-full text-slate-600 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mr-2" /> K线加载中...
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Screen 4 — 资金流向
// ============================================================
interface FlowRow { [key: string]: string | number }
interface SectorRankings { rankings?: { name: string }[] }

function ScreenCapitalFlow({ data }: { data: DashboardV2Data }): React.ReactElement {
  const cf = data.capitalFlow;
  const mainForce = cf?.mainForce as Record<string, unknown> | undefined;

  // Try to extract capital flow data
  const flowRows: FlowRow[] = (mainForce?.flow as FlowRow[]) || [];
  const summary = (mainForce?.summary as Record<string, number>) || {};
  const sectorRankings = cf?.sectorRankings as SectorRankings | undefined;

  return (
    <div className="card p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <ArrowDownToLine className="w-4 h-4 text-blue-400" />
        <h3 className="section-title">资金流向</h3>
        <span className="badge badge-blue text-[10px] ml-auto">主力资金</span>
      </div>

      {/* 汇总指标 */}
      {Object.keys(summary).length > 0 && (
        <div className="grid grid-cols-2 gap-2 mb-3">
          {Object.entries(summary).slice(0, 4).map(([k, v]) => (
            <div key={k} className="bg-[#0b1120] rounded p-2 border border-[#151d2e]">
              <div className="text-[9px] text-slate-500">{k}</div>
              <div className={cn("text-xs font-mono font-bold", typeof v === "number" && v >= 0 ? "text-emerald-400" : "text-red-400")}>
                {typeof v === "number" ? FMT(v / 1e8, 1) + "亿" : String(v)}
              </div>
            </div>
          ))}
        </div>
      )}

      {((): React.ReactNode => {
        if (flowRows.length > 0) {
          return (
            <div className="flex-1 overflow-auto">
              <table className="data-table text-[10px]">
                <thead><tr>
                  {Object.keys(flowRows[0]).slice(0, 5).map((k) => <th key={k}>{k}</th>)}
                </tr></thead>
                <tbody>
                  {flowRows.slice(0, 10).map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).slice(0, 5).map((v, j) => (
                        <td key={j} className="font-mono">{typeof v === "number" ? FMT(v, 0) : String(v).slice(0, 12)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return (
          <div className="flex-1 flex items-center justify-center text-slate-600 text-xs">
            资金流向数据加载中...
          </div>
        );
      })()}

      {/* Sector rankings if available */}
      {sectorRankings?.rankings && sectorRankings.rankings.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[#151d2e]">
          <div className="text-[10px] text-slate-500 mb-1">行业轮动</div>
          <div className="flex flex-wrap gap-1">
            {sectorRankings.rankings.slice(0, 6).map((s, i) => (
              <span key={i} className="badge badge-cyan text-[9px]">{s.name}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// Screen 5 — 风险监控
// ============================================================
function ScreenRiskMonitor({ data }: { data: DashboardV2Data }) {
  const alerts = data.alerts?.items || [];
  const total = data.alerts?.total || 0;

  return (
    <div className="card p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <ShieldAlert className="w-4 h-4 text-amber-400" />
        <h3 className="section-title">风险监控</h3>
        {total > 0 && <span className="badge badge-yellow text-[10px] ml-auto">{total} 条预警</span>}
      </div>

      {alerts.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-600">
          <ShieldAlert className="w-8 h-8 mb-2 opacity-30" />
          <p className="text-xs">暂无活跃预警</p>
          <p className="text-[10px] mt-0.5">系统监控中...</p>
        </div>
      ) : (
        <div className="flex-1 overflow-auto space-y-2">
          {alerts.slice(0, 10).map((alert) => {
            const Icon = SEVERITY_ICON[alert.severity] || Info;
            const sevColor = alert.severity === "critical" ? "text-red-400" : alert.severity === "warning" ? "text-amber-400" : "text-blue-400";
            return (
              <div key={alert.id} className="bg-[#0b1120] rounded-lg p-2.5 border border-[#151d2e] flex items-start gap-2">
                <Icon className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", sevColor)} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className={cn("badge text-[8px]", SEVERITY_BADGE[alert.severity] || "badge-gray")}>
                      {alert.type}
                    </span>
                    {alert.code && <span className="font-mono text-[10px] text-cyan-400">{alert.code}</span>}
                  </div>
                  <p className="text-[11px] text-slate-300 mt-0.5 line-clamp-2">{alert.title || alert.message}</p>
                  <p className="text-[9px] text-slate-600 mt-0.5">{alert.createdAt?.slice(0, 16)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============================================================
// Screen 6 — 组合管理
// ============================================================
interface PositionRow {
  code?: string; name?: string; marketValue?: number; mv?: number;
  unrealizedPnlPct?: number; pnlPct?: number;
}

function ScreenPortfolioPanel({ data }: { data: DashboardV2Data }) {
  const pf = data.portfolio;
  const positions: PositionRow[] = (pf?.positions || []) as PositionRow[];
  const equityCurve = pf?.equityCurve || [];

  // Equity curve mini sparkline
  const eqPoints = useMemo(() => {
    if (equityCurve.length < 2) return "";
    const vals = equityCurve.map((p) => p.value);
    const max = Math.max(...vals), min = Math.min(...vals), r = max - min || 1;
    return vals.map((v, i) => `${(i / (vals.length - 1)) * 100},${100 - ((v - min) / r) * 80}`).join(" ");
  }, [equityCurve]);

  return (
    <div className="card p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <Briefcase className="w-4 h-4 text-emerald-400" />
        <h3 className="section-title">组合管理</h3>
        <span className="badge badge-gray text-[10px] ml-auto">{pf?.dataSource === "westock" ? "实盘" : "模拟"}</span>
      </div>

      {/* 资产概览 KPI */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <KpiMini label="总资产" value={pf?.totalAssets} fmt="money" />
        <KpiMini label="今日盈亏" value={pf?.todayPnl} fmt="pnl" pct={pf?.todayPnlPct} />
        <KpiMini label="累计盈亏" value={pf?.totalPnl} fmt="pnl" />
      </div>

      {/* Equity curve mini */}
      {equityCurve.length > 1 && (
        <div className="mb-3 p-2 bg-[#0b1120] rounded-lg border border-[#151d2e]">
          <div className="text-[10px] text-slate-500 mb-1">净值曲线</div>
          <svg viewBox="0 0 100 40" className="w-full h-10" preserveAspectRatio="none">
            <polyline fill="none" stroke="#34d399" strokeWidth="1.2" points={eqPoints} />
          </svg>
        </div>
      )}

      {/* 持仓表格 */}
      <div className="flex-1 overflow-auto">
        <table className="data-table text-[11px]">
          <thead><tr><th>代码</th><th>名称</th><th>市值</th><th>盈亏%</th></tr></thead>
          <tbody>
            {positions.length > 0 ? positions.map((pos, i) => {
              const pnlPct = pos.unrealizedPnlPct || pos.pnlPct || 0;
              const mv = pos.marketValue || pos.mv || 0;
              return (
                <tr key={i}>
                  <td className="font-mono text-slate-300">{(pos.code || "").replace(/\.(SH|SZ)$/, "")}</td>
                  <td className="text-slate-400 text-xs">{pos.name || "—"}</td>
                  <td className="font-mono text-slate-300">¥{FMT(mv, 0)}</td>
                  <td className={cn("font-mono", pnlPct >= 0 ? "text-emerald-400" : "text-red-400")}>{PCT(pnlPct)}</td>
                </tr>
              );
            }) : (
              <tr><td colSpan={4} className="text-center text-slate-600 text-xs py-4">暂无持仓数据</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KpiMini({ label, value, fmt, pct }: { label: string; value?: number; fmt: "money" | "pnl"; pct?: number }) {
  if (value == null) return null;
  const absVal = Math.abs(value);
  const display = fmt === "money" ? `¥${FMT(value, 0)}` : `${value >= 0 ? "+" : ""}${FMT(value, 0)}`;
  const color = value >= 0 ? "text-emerald-400" : "text-red-400";
  return (
    <div className="bg-[#0b1120] rounded p-2 border border-[#151d2e] text-center">
      <div className="text-[9px] text-slate-500">{label}</div>
      <div className={cn("text-xs font-bold font-mono", color)}>{display}</div>
      {pct != null && <div className={cn("text-[9px] font-mono", pct >= 0 ? "text-emerald-400" : "text-red-400")}>{PCT(pct)}</div>}
    </div>
  );
}

// ============================================================
// Dashboard V2 主页面 — 六屏矩阵
// ============================================================
export default function DashboardPage() {
  const [data, setData] = useState<DashboardV2Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    fetchDashboardV2()
      .then((d) => { setData(d); setError(""); setLastUpdate(new Date().toLocaleTimeString("zh-CN")); })
      .catch((e) => setError(e.message || "数据加载失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  // Loading state
  if (loading && !data) return (
    <div className="flex items-center justify-center h-[70vh]">
      <div className="text-center">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-cyan-400" />
        <p className="text-slate-400 text-sm">加载实时行情数据...</p>
        <p className="text-slate-600 text-xs mt-1">市场温度 · AI研判 · K线 · 资金流 · 预警 · 组合</p>
      </div>
    </div>
  );

  // Error with retry
  if (!data && error) return (
    <div className="flex items-center justify-center h-[70vh]">
      <div className="text-center">
        <AlertTriangle className="w-10 h-10 mx-auto mb-3 text-amber-400" />
        <p className="text-slate-300 text-sm">数据加载失败</p>
        <p className="text-slate-600 text-xs mt-1 mb-3">{error}</p>
        <button onClick={load} className="btn-primary text-xs">重试</button>
      </div>
    </div>
  );

  if (!data) return null;

  const t = data.temperature;
  const j = data.judgment;
  const scoreColor = t.score >= 70 ? "#ef4444" : t.score >= 50 ? "#fbbf24" : t.score >= 30 ? "#3b82f6" : "#34d399";

  return (
    <div className="space-y-4 animate-slide-up">
      {/* ===== Header ===== */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">AI 量化驾驶舱</h1>
          <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
            六屏矩阵 · 实时监控
            {data._meta.westockAvailable && <span className="badge badge-green text-[10px]">行情在线</span>}
            {lastUpdate && <span className="text-[10px] text-slate-600">更新 {lastUpdate}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="btn-secondary flex items-center gap-1.5 text-xs">
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} /> 刷新
          </button>
        </div>
      </div>

      {/* ===== Top KPI Row ===== */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiTopCard icon={<CircleDollarSign className="w-4 h-4" />} label="总资产"
          value={`¥${FMT(data.portfolio.totalAssets, 0)}`} sub={`${PCT(data.portfolio.todayPnlPct)} 今日`}
          color="#22d3ee" />
        <KpiTopCard icon={data.portfolio.todayPnl >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />} label="今日盈亏"
          value={`${data.portfolio.todayPnl >= 0 ? "+" : ""}¥${FMT(data.portfolio.todayPnl, 0)}`}
          sub={PCT(data.portfolio.todayPnlPct)}
          color={data.portfolio.todayPnl >= 0 ? "#34d399" : "#f87171"} />
        <KpiTopCard icon={<Thermometer className="w-4 h-4" />} label="市场温度"
          value={`${t.score.toFixed(0)}/100`} sub={t.riskLabel}
          color={scoreColor} />
        <KpiTopCard icon={<Brain className="w-4 h-4" />} label="AI评分"
          value={`${j?.aiScore ?? "--"}/100`} sub={j?.marketTrend || "研判中"}
          color={j?.aiScore && j.aiScore >= 60 ? "#34d399" : j?.aiScore && j.aiScore >= 40 ? "#fbbf24" : "#f87171"} />
        <KpiTopCard icon={<ShieldAlert className="w-4 h-4" />} label="活跃预警"
          value={`${data.alerts?.total ?? 0}`} sub="实时监控"
          color={data.alerts?.total > 0 ? "#ef4444" : "#34d399"} />
      </div>

      {/* ===== Six-Screen Matrix ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* 屏1: 市场概览 (5 cols) */}
        <div className="lg:col-span-5 min-h-[320px]">
          <ScreenMarketOverview data={data} />
        </div>

        {/* 屏2: AI 研判 (7 cols) */}
        <div className="lg:col-span-7 min-h-[320px]">
          <ScreenAIJudgment data={data} />
        </div>

        {/* 屏3: K线信号 (8 cols) */}
        <div className="lg:col-span-8 min-h-[380px]">
          <ScreenKlineSignals data={data} />
        </div>

        {/* 屏4: 资金流向 (4 cols) */}
        <div className="lg:col-span-4 min-h-[380px]">
          <ScreenCapitalFlow data={data} />
        </div>

        {/* 屏5: 风险监控 (5 cols) */}
        <div className="lg:col-span-5 min-h-[300px]">
          <ScreenRiskMonitor data={data} />
        </div>

        {/* 屏6: 组合管理 (7 cols) */}
        <div className="lg:col-span-7 min-h-[300px]">
          <ScreenPortfolioPanel data={data} />
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Top KPI Card
// ============================================================
function KpiTopCard({ icon, label, value, sub, color }: {
  icon: React.ReactNode; label: string; value: string; sub: string; color: string;
}) {
  return (
    <div className="card p-3 flex items-center gap-3">
      <div className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${color}15` }}>
        <span style={{ color }}>{icon}</span>
      </div>
      <div className="min-w-0">
        <div className="text-[10px] text-slate-500">{label}</div>
        <div className="text-sm font-bold text-slate-100 font-mono">{value}</div>
        <div className="text-[10px] text-slate-500">{sub}</div>
      </div>
    </div>
  );
}
