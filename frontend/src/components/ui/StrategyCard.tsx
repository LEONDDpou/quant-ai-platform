"use client";

import { useRouter } from "next/navigation";
import { Play, Pause, Square, FlaskConical, Eye, Edit3, TrendingUp, Shield, Target, Clock, FileText, Archive, Trash2 } from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { cn, formatPct } from "@/lib/utils";

export interface StrategyCardData {
  id: string;
  name: string;
  type: string;
  status: "running" | "stopped" | "paused" | "archived" | "backtesting";
  annualizedReturn: number; // 收益率
  maxDrawdown: number;     // 最大回撤
  winRate: number;         // 胜率
  sharpeRatio?: number;
  tags?: string[];
  description?: string;
  equityCurve?: number[];
  pnlAmount?: string;      // e.g. "+$51,842"
  tradesCount?: number;
}

interface StrategyCardProps {
  strategy: StrategyCardData;
  risk?: "low" | "mid" | "high";
  rank?: number;
  onToggle?: (id: string) => void;
  onView?: (id: string) => void;
  onEdit?: (id: string) => void;
  onBacktest?: (id: string) => void;
  onArchive?: (id: string) => void;
  onDelete?: (id: string) => void;
}

const statusConfig = {
  running:   { label: "运行中", cls: "badge-running", dotCls: "bg-emerald-400" },
  stopped:   { label: "已停止", cls: "badge-gray", dotCls: "bg-slate-500" },
  paused:    { label: "已暂停", cls: "badge-paused", dotCls: "bg-amber-400" },
  archived:  { label: "已归档", cls: "badge-archived", dotCls: "bg-slate-600" },
  backtesting:{ label: "回测中", cls: "badge-blue", dotCls: "bg-blue-400" },
};

function areaChartOption(data: number[], color = "#34d399"): EChartsOption {
  return {
    backgroundColor: "transparent",
    grid: { top: 5, right: 5, bottom: 5, left: 30 },
    xAxis: { type: "category", show: false, data: data.map((_, i) => i) },
    yAxis: { type: "value", show: false, min: Math.min(...data) * 0.98, max: Math.max(...data) * 1.02 },
    series: [{
      type: "line", data, smooth: true, symbol: "none",
      lineStyle: { color, width: 1.5 },
      areaStyle: {
        color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: color.replace(")", ",0.25)").replace("rgb", "rgba").replace("#", "rgba(").replace(/([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i, (m,r,g,b) => `${parseInt(r,16)},${parseInt(g,16)},${parseInt(b,16)},0.15`) },
            { offset: 1, color: "transparent" },
          ],
        },
      },
    }],
    tooltip: { show: false },
  };
}

// Quick fix for the area style color
function safeAreaColor(color: string): any {
  // Simple approach - just use rgba
  if (color.startsWith("#") && color.length === 7) {
    const r = parseInt(color.slice(1,3),16);
    const g = parseInt(color.slice(3,5),16);
    const b = parseInt(color.slice(5,7),16);
    return {
      type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1,
      colorStops: [
        { offset: 0, color: `rgba(${r},${g},${b},0.2)` },
        { offset: 1, color: `rgba(${r},${g},${b},0)` },
      ],
    };
  }
  return { type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [{ offset: 0, color: "rgba(52,211,153,0.2)" }, { offset: 1, color: "transparent" }] };
}

function buildAreaOption(data: number[], color = "#34d399"): EChartsOption {
  return {
    backgroundColor: "transparent",
    grid: { top: 4, right: 4, bottom: 4, left: 28 },
    xAxis: { type: "category", show: false, data: data.map((_, i) => i) },
    yAxis: { type: "value", show: false, scale: true },
    series: [{
      type: "line", data, smooth: true, symbol: "none",
      lineStyle: { color, width: 1.5 },
      areaStyle: { color: safeAreaColor(color) },
    }],
    tooltip: { show: false },
  };
}

export function StrategyCard({ strategy, risk, rank, onToggle, onView, onEdit, onBacktest, onArchive, onDelete }: StrategyCardProps) {
  const s = strategy;
  const st = statusConfig[s.status] || statusConfig.stopped;
  const router = useRouter();
  const riskMeta = {
    low: { label: "低风险", cls: "text-emerald-400" },
    mid: { label: "中风险", cls: "text-amber-400" },
    high: { label: "高风险", cls: "text-rose-400" },
  }[risk ?? "low"];

  const chartColor =
    s.status === "running" ? "#34d399" :
    s.status === "paused" ? "#fbbf24" :
    s.status === "backtesting" ? "#60a5fa" : "#64748b";

  // 真实数据始终带 equityCurve；缺失时回退到空序列避免 SSR/CSR 不一致
  const equityData = s.equityCurve && s.equityCurve.length ? s.equityCurve : [];

  const canToggle = (s.status === "running" || s.status === "stopped" || s.status === "paused") && onToggle;

  return (
    <div className="card p-4 group">
      {/* Header row */}
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={cn("badge", st.cls)}>
              <span className={cn("w-1.5 h-1.5 rounded-full mr-1", st.dotCls, s.status === "running" && "animate-pulse-glow")} />
              {st.label}
            </span>
            {rank != null && (
              <span className="badge badge-purple text-[9px]">#{rank}</span>
            )}
            {risk && (
              risk === "high" ? (
                <button
                  onClick={() => router.push("/dashboard")}
                  title="查看平台风险监控"
                  className={cn("text-[10px] font-medium underline-offset-2 hover:underline", riskMeta.cls)}
                >{riskMeta.label} ↗</button>
              ) : (
                <span className={cn("text-[10px] font-medium", riskMeta.cls)}>{riskMeta.label}</span>
              )
            )}
            {/* Toggle for running / stopped / paused */}
            {canToggle && (
              <button
                onClick={() => onToggle!(s.id)}
                className={cn(
                  "w-8 h-4 rounded-full transition-colors relative cursor-pointer",
                  s.status === "running" ? "bg-emerald-500/30" : "bg-slate-600/30"
                )}
                title={s.status === "running" ? "停止策略" : "启动策略"}
              >
                <span className={cn(
                  "absolute top-0.5 w-3 h-3 rounded-full transition-all",
                  s.status === "running" ? "right-0.5 bg-emerald-400" : "left-0.5 bg-slate-500"
                )} />
              </button>
            )}
          </div>
          <h3 className="text-sm font-semibold text-slate-100 mt-1.5 truncate">{s.name}</h3>
          {s.description && (
            <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">{s.description}</p>
          )}
        </div>
        {s.type && (
          <span className="tag ml-2 flex-shrink-0">{s.type}</span>
        )}
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <MetricBox icon={<TrendingUp className="w-3 h-3" />} label="收益率" value={formatPct(s.annualizedReturn)} positive={s.annualizedReturn > 0} />
        <MetricBox icon={<Shield className="w-3 h-3" />} label="最大回撤" value={formatPct(s.maxDrawdown, false)} positive={false} />
        <MetricBox icon={<Target className="w-3 h-3" />} label="胜率" value={`${s.winRate}%`} positive={s.winRate > 50} />
      </div>

      {/* Area chart */}
      <div className="mb-3 h-14">
        <ReactECharts option={buildAreaOption(equityData, chartColor)} style={{ height: "100%", width: "100%" }} />
      </div>

      {/* Bottom: Tags + Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 flex-wrap">
          {s.tags?.map((t) => (
            <span key={t} className="tag">{t}</span>
          ))}
          {s.tradesCount != null && (
            <span className="text-[10px] text-slate-600 flex items-center gap-0.5">
              <Clock className="w-2.5 h-2.5" /> {s.tradesCount} 笔交易
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onView && (
            <button onClick={() => onView(s.id)} className="btn-ghost" title="查看详情与报告">详情</button>
          )}
          {onEdit && s.status !== "running" && (
            <button onClick={() => onEdit(s.id)} className="btn-ghost">编辑</button>
          )}
          {onBacktest && (
            <button onClick={() => onBacktest(s.id)} className="btn-ghost">回测</button>
          )}
          {onArchive && s.status !== "archived" && (
            <button onClick={() => onArchive(s.id)} className="btn-ghost flex items-center gap-0.5">
              <Archive className="w-3 h-3" />归档
            </button>
          )}
          {onDelete && (
            <button onClick={() => onDelete(s.id)} className="btn-ghost text-rose-400 flex items-center gap-0.5">
              <Trash2 className="w-3 h-3" />删除
            </button>
          )}
        </div>
      </div>

      {/* PnL amount shown if available */}
      {s.pnlAmount && (
        <div className="mt-2 pt-2 border-t border-[#1e2a3d] flex items-center justify-between">
          <span className="text-[11px] text-slate-500">当前盈亏</span>
          <span className={cn("font-mono font-bold text-sm", s.annualizedReturn >= 0 ? "pos" : "neg")}>
            {s.pnlAmount}
          </span>
        </div>
      )}
    </div>
  );
}

function MetricBox({
  icon, label, value, positive,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="bg-[#0d1220] rounded-lg px-2 py-1.5">
      <div className="flex items-center gap-1 text-[10px] text-slate-500 mb-0.5">
        {icon} {label}
      </div>
      <div className={cn("font-mono font-semibold text-xs", positive !== false ? "pos" : "neg")}>
        {value}
      </div>
    </div>
  );
}
