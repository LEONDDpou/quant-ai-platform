"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import {
  RefreshCw,
  CandlestickChart,
  DollarSign,
  AlertTriangle,
  Zap,
  Server,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchMarketRealtime,
  fetchMarketKline,
  fetchMarketCapitalFlow,
  fetchMarketSources,
  type MarketRealtimeResponse,
  type MarketRealtimeItem,
  type MarketKlineBar,
  type MarketCapitalFlow,
  type MarketSourceHealth,
} from "@/lib/api";
import { useMarketRealtimeSocket } from "@/hooks/useMarketRealtimeSocket";

// ============================================================
// 常量 & 工具
// ============================================================
const DEFAULT_WATCHLIST = ["600519", "000858", "600036", "000001", "300750", "601318"];
const KLINE_PERIODS = [
  { key: "intraday", label: "分时" },
  { key: "5m", label: "5分" },
  { key: "15m", label: "15分" },
  { key: "30m", label: "30分" },
  { key: "day", label: "日K" },
  { key: "week", label: "周K" },
  { key: "month", label: "月K" },
] as const;

function fmtPct(v: number): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}
function fmtPrice(v: number): string {
  return v > 0 ? v.toFixed(2) : "—";
}
function fmtFlow(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (abs >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
}
function fmtMv(v: number): string {
  if (v >= 1e12) return `${(v / 1e12).toFixed(2)}万亿`;
  if (v >= 1e8) return `${(v / 1e8).toFixed(0)}亿`;
  return `${(v / 1e4).toFixed(0)}万`;
}
function riskBadgeClass(level: string): string {
  if (level === "high") return "bg-red-500/15 text-red-400 border border-red-500/30";
  if (level === "mid") return "bg-amber-500/15 text-amber-400 border border-amber-500/30";
  return "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30";
}
function riskLabel(level: string): string {
  if (level === "high") return "高风险";
  if (level === "mid") return "中度";
  return "低风险";
}

// ============================================================
// 子组件：数据源健康
// ============================================================
function SourceHealthCard({ sources }: { sources: MarketSourceHealth[] | null }) {
  if (!sources) return null;
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Server className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-bold text-slate-200">数据源健康</span>
        <span className="text-[10px] text-slate-600 ml-auto">故障切换编排</span>
      </div>
      <div className="p-3 grid grid-cols-2 gap-2">
        {sources.map((s) => {
          const circuitOk = s.circuit === "closed";
          return (
            <div
              key={s.name}
              className={cn(
                "flex items-center justify-between px-3 py-2 rounded-lg border",
                circuitOk ? "bg-emerald-500/5 border-emerald-500/20" : "bg-red-500/5 border-red-500/20",
              )}
            >
              <div className="flex items-center gap-2">
                <span className={cn("w-1.5 h-1.5 rounded-full", circuitOk ? "bg-emerald-400" : "bg-red-400")} />
                <span className="text-xs text-slate-300 font-mono">{s.name}</span>
              </div>
              <span className={cn("text-[10px] font-mono", circuitOk ? "text-emerald-400" : "text-red-400")}>
                {s.circuit}
                {s.lastUsed ? " · 在用" : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// 子组件：AI 评分 + 风险预警
// ============================================================
function AIScorePanel({
  items,
  onSelect,
}: {
  items: MarketRealtimeItem[];
  onSelect: (code: string) => void;
}) {
  const highRisk = items.filter((i) => i.aiScore.riskLevel === "high");
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Zap className="w-4 h-4 text-amber-400" />
        <span className="text-sm font-bold text-slate-200">AI 量化评分</span>
        <span className="text-[10px] text-slate-600 ml-auto">透明启发式 · 非投资建议</span>
      </div>
      {highRisk.length > 0 && (
        <div className="flex items-start gap-2 px-4 py-2 bg-red-500/10 border-b border-red-500/20">
          <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-red-300 leading-relaxed">
            风险预警：{highRisk.map((h) => `${h.quote.name}(${fmtPct(h.quote.changePct)})`).join("、")}
            {" "}触发高风险阈值（RSI 极端 / 涨跌幅≥9.5%）。
          </p>
        </div>
      )}
      <div className="divide-y divide-[#151d2e] max-h-[420px] overflow-y-auto">
        {items.map((it) => (
          <button
            key={it.quote.code}
            onClick={() => onSelect(it.quote.code)}
            className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[#0d1220] transition-colors text-left"
          >
            <div className="flex-1 min-w-0">
              <div className="text-xs text-slate-200 font-medium truncate">{it.quote.name}</div>
              <div className="text-[10px] text-slate-500 font-mono">{it.quote.code}</div>
            </div>
            <div className="relative w-11 h-11 flex-shrink-0">
              <svg viewBox="0 0 44 44" className="w-11 h-11 -rotate-90">
                <circle cx="22" cy="22" r="18" fill="none" stroke="#1a2233" strokeWidth="4" />
                <circle
                  cx="22" cy="22" r="18" fill="none"
                  stroke={it.aiScore.score >= 60 ? "#34d399" : it.aiScore.score >= 45 ? "#fbbf24" : "#f87171"}
                  strokeWidth="4" strokeLinecap="round"
                  strokeDasharray={`${(it.aiScore.score / 100) * 113} 113`}
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold font-mono text-slate-200">
                {it.aiScore.score.toFixed(0)}
              </span>
            </div>
            <span className={cn("text-[10px] px-2 py-0.5 rounded font-medium flex-shrink-0", riskBadgeClass(it.aiScore.riskLevel))}>
              {riskLabel(it.aiScore.riskLevel)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 子组件：K 线图（ECharts 蜡烛 + 成交量）
// ============================================================
function KlineChart({ bars, period }: { bars: MarketKlineBar[]; period: string }) {
  const option: EChartsOption = useMemo(() => {
    const dates = bars.map((b) => b.dt);
    const candle = bars.map((b) => [b.open, b.close, b.low, b.high]);
    const volumes = bars.map((b) => ({
      value: b.volume,
      itemStyle: { color: b.close >= b.open ? "rgba(239,68,68,0.55)" : "rgba(34,197,94,0.55)" },
    }));
    return {
      backgroundColor: "transparent",
      animation: false,
      legend: { show: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1a1f2e",
        borderColor: "#2a3142",
        textStyle: { color: "#e2e8f0", fontSize: 12 },
        axisPointer: { type: "cross", lineStyle: { color: "#475569" } },
      },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      grid: [
        { left: 56, right: 16, top: 16, height: "62%" },
        { left: 56, right: 16, top: "74%", height: "16%" },
      ],
      xAxis: [
        {
          type: "category", data: dates, boundaryGap: true,
          axisLine: { lineStyle: { color: "#2a3142" } },
          axisLabel: { color: "#64748b", fontSize: 10, showMaxLabel: true },
          axisTick: { show: false }, splitLine: { show: false },
        },
        {
          type: "category", gridIndex: 1, data: dates, boundaryGap: true,
          axisLine: { lineStyle: { color: "#2a3142" } },
          axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          scale: true, position: "right", axisLine: { show: false },
          splitLine: { lineStyle: { color: "#141a28" } }, axisLabel: { color: "#64748b", fontSize: 10 },
        },
        { gridIndex: 1, scale: true, position: "right", axisLine: { show: false }, splitLine: { show: false }, axisLabel: { show: false } },
      ],
      series: [
        {
          name: "K线", type: "candlestick", data: candle,
          itemStyle: { color: "#ef4444", color0: "#22c55e", borderColor: "#ef4444", borderColor0: "#22c55e" },
        },
        { name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: volumes },
      ],
    };
  }, [bars]);

  if (!bars || bars.length === 0) {
    return <div className="flex items-center justify-center h-[360px] text-xs text-slate-600">暂无 {period} K 线数据</div>;
  }
  return <ReactECharts option={option} style={{ height: 400, width: "100%" }} notMerge />;
}

// ============================================================
// 子组件：资金流柱状图
// ============================================================
function CapitalFlowChart({ flow }: { flow: MarketCapitalFlow | null }) {
  const option: EChartsOption = useMemo(() => {
    const cats = ["主力净流入", "超大单", "大单", "中单", "小单"];
    const vals = flow ? [flow.mainIn, flow.ultraLarge, flow.large, flow.medium, flow.small] : [0, 0, 0, 0, 0];
    return {
      backgroundColor: "transparent",
      grid: { left: 70, right: 20, top: 20, bottom: 24 },
      tooltip: {
        trigger: "axis", backgroundColor: "#1a1f2e", borderColor: "#2a3142",
        textStyle: { color: "#e2e8f0", fontSize: 12 },
        formatter: (p: any) => `${p[0].name}<br/>${fmtFlow(p[0].value)}`,
      },
      xAxis: { type: "value", axisLabel: { color: "#64748b", fontSize: 10, formatter: (v: number) => fmtFlow(v) }, splitLine: { lineStyle: { color: "#141a28" } } },
      yAxis: { type: "category", data: cats, axisLabel: { color: "#94a3b8", fontSize: 11 }, axisLine: { lineStyle: { color: "#2a3142" } } },
      series: [
        {
          type: "bar",
          data: vals.map((v) => ({ value: v, itemStyle: { color: v >= 0 ? "#ef4444" : "#22c55e", borderRadius: [0, 3, 3, 0] } })),
          barWidth: "55%",
          label: { show: true, position: "right", color: "#94a3b8", fontSize: 10, formatter: (p: any) => fmtFlow(p.value) },
        },
      ],
    };
  }, [flow]);

  if (!flow || !flow.available) {
    return <div className="flex items-center justify-center h-[300px] text-xs text-slate-600">该标的资金流数据暂不可用</div>;
  }
  return <ReactECharts option={option} style={{ height: 320, width: "100%" }} notMerge />;
}

// ============================================================
// 实时行情表：逐行 memo，值变化才重渲染（消灭整表闪烁）
// ============================================================
interface RowProps {
  code: string;
  name: string;
  price: number;
  changePct: number;
  volume: number;
  amount: number;
  turnover: number;
  pe: number;
  totalMv: number;
  score: number;
  selected: boolean;
  onSelect: (code: string) => void;
}

// 价格变化时的"轻微高亮过渡"——用 1 帧淡出背景，观感平滑而非突兀闪烁
function RealtimeQuoteRowBase({
  code, name, price, changePct, volume, amount, turnover, pe, totalMv, score, selected, onSelect,
}: RowProps) {
  const prevPrice = useRef(price);
  const [flash, setFlash] = useState<"" | "up" | "down">("");

  useEffect(() => {
    if (price !== prevPrice.current) {
      const dir = price > prevPrice.current ? "up" : "down";
      prevPrice.current = price;
      setFlash(dir);
      const t = setTimeout(() => setFlash(""), 450);
      return () => clearTimeout(t);
    }
  }, [price]);

  const colorCls = changePct > 0 ? "text-red-400" : changePct < 0 ? "text-green-400" : "text-slate-500";
  const flashBg = flash === "up" ? "bg-red-500/[0.08]" : flash === "down" ? "bg-green-500/[0.08]" : "";

  return (
    <tr
      onClick={() => onSelect(code)}
      className={cn(
        "cursor-pointer transition-colors duration-300",
        selected ? "bg-cyan-500/10" : flashBg || "hover:bg-[#0d1220]",
      )}
    >
      <td className="px-4 py-2.5">
        <span className="text-slate-200 font-medium">{name}</span>
        <span className="text-slate-600 ml-1 text-[9px] font-mono">{code}</span>
      </td>
      <td className={cn("px-3 py-2.5 text-right font-mono font-bold tabular-nums transition-colors duration-300", colorCls)}>
        {fmtPrice(price)}
      </td>
      <td className={cn("px-3 py-2.5 text-right font-mono font-medium tabular-nums transition-colors duration-300", colorCls)}>
        {fmtPct(changePct)}
      </td>
      <td className="px-3 py-2.5 text-right font-mono text-slate-400 hidden md:table-cell tabular-nums">
        {(volume / 1e4).toFixed(1)}
      </td>
      <td className="px-3 py-2.5 text-right font-mono text-slate-400 hidden lg:table-cell tabular-nums">{fmtFlow(amount)}</td>
      <td className="px-3 py-2.5 text-right font-mono text-slate-400 hidden lg:table-cell tabular-nums">{turnover.toFixed(2)}%</td>
      <td className="px-3 py-2.5 text-right font-mono text-slate-400 hidden xl:table-cell tabular-nums">{pe > 0 ? pe.toFixed(1) : "—"}</td>
      <td className="px-3 py-2.5 text-right font-mono text-slate-400 hidden xl:table-cell tabular-nums">{fmtMv(totalMv)}</td>
      <td className="px-3 py-2.5 text-right hidden xl:table-cell">
        <span className={cn("text-xs font-bold font-mono", score >= 60 ? "text-emerald-400" : score >= 45 ? "text-amber-400" : "text-red-400")}>
          {score.toFixed(0)}
        </span>
      </td>
    </tr>
  );
}

const RealtimeQuoteRow = React.memo(RealtimeQuoteRowBase);

// ============================================================
// 把 WS 实时价合入 REST 快照（仅覆盖价/量，技术/AI/资金保留 REST 结果）
// ============================================================
function buildDisplayItems(
  rt: MarketRealtimeResponse | null,
  wsByCode: Record<string, any>,
  wsLastTs: string | null,
): MarketRealtimeItem[] {
  if (!rt) return [];
  const now = wsLastTs ? new Date(wsLastTs.replace(/-/g, "/")).getTime() : 0;
  return rt.items.map((it) => {
    const live = wsByCode[it.quote.code];
    if (live && now && Math.abs(Date.now() - now) < 60000) {
      return {
        ...it,
        quote: {
          ...it.quote,
          price: live.price || it.quote.price,
          change: live.change || it.quote.change,
          changePct: live.change_pct ?? it.quote.changePct,
          volume: live.volume ?? it.quote.volume,
          amount: live.amount ?? it.quote.amount,
        },
      };
    }
    return it;
  });
}

// ============================================================
// 主组件（已去重：涨跌排行榜 / 市场宽度 因与「A股实时动态」重复而移除，
// 保留实时行情表 / AI 评分 / 数据源健康 / K线 / 个股资金流 等独有功能）
// ============================================================
export default function RealtimeMarketPanel({ embedded = false }: { embedded?: boolean }) {
  const [codes, setCodes] = useState<string[]>(DEFAULT_WATCHLIST);
  const [selected, setSelected] = useState<string>("600519");

  const [rt, setRt] = useState<MarketRealtimeResponse | null>(null);
  const [kline, setKline] = useState<MarketKlineBar[]>([]);
  const [capFlow, setCapFlow] = useState<MarketCapitalFlow | null>(null);
  const [sources, setSources] = useState<MarketSourceHealth[] | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState<string>("day");
  const [countdown, setCountdown] = useState(5);
  const [refreshInterval, setRefreshInterval] = useState(5);

  const ws = useMarketRealtimeSocket();
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // onSelect 稳定引用，避免 memo 行因回调变化而全部重渲染
  const handleSelect = useCallback((code: string) => setSelected(code), []);

  const loadSnapshot = useCallback(async () => {
    setError("");
    if (!rt) setLoading(true);
    try {
      const data = await fetchMarketRealtime(codes);
      setRt(data);
      setCountdown(refreshInterval);
    } catch (e: unknown) {
      if (!rt) setError(e instanceof Error ? e.message : "实时行情加载失败");
    } finally {
      setLoading(false);
    }
  }, [codes, rt, refreshInterval]);

  const loadDetail = useCallback(async () => {
    try {
      const [k, cf] = await Promise.all([
        fetchMarketKline(selected, period, period === "intraday" ? 240 : 120),
        fetchMarketCapitalFlow([selected]),
      ]);
      setKline(k);
      setCapFlow(cf.items.find((x) => x.code === selected) ?? null);
    } catch {
      /* 详情失败不阻塞主表 */
    }
  }, [selected, period]);

  const loadSources = useCallback(async () => {
    try {
      setSources(await fetchMarketSources());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadSnapshot();
    loadDetail();
    loadSources();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    loadSnapshot();
  }, [loadSnapshot]);

  useEffect(() => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (refreshRef.current) clearInterval(refreshRef.current);
    countdownRef.current = setInterval(() => {
      setCountdown((p) => (p <= 1 ? refreshInterval : p - 1));
    }, 1000);
    refreshRef.current = setInterval(() => {
      loadSnapshot();
    }, refreshInterval * 1000);
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (refreshRef.current) clearInterval(refreshRef.current);
    };
  }, [loadSnapshot, refreshInterval]);

  const displayItems = useMemo(() => buildDisplayItems(rt, ws.byCode, ws.lastTs), [rt, ws.byCode, ws.lastTs]);

  const selectedName = displayItems.find((i) => i.quote.code === selected)?.quote.name ?? selected;
  const selectedItem = displayItems.find((i) => i.quote.code === selected);
  const fmtCountdown = (s: number) => `0:${s.toString().padStart(2, "0")}`;

  const wsStatusBadge = (
    <span
      className={cn(
        "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono",
        ws.status === "open" ? "bg-emerald-500/10 text-emerald-400" : ws.status === "error" ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400",
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", ws.status === "open" ? "bg-emerald-400" : ws.status === "error" ? "bg-red-400" : "bg-amber-400 animate-pulse")} />
      {ws.status === "open" ? "WS 实时连接" : ws.status === "error" ? "WS 断开" : "WS 连接中"}
    </span>
  );

  return (
    <div className="space-y-5">
      {!embedded && (
        <div className="sticky top-0 z-20 bg-[#070b14]/95 backdrop-blur border-b border-[#151d2e] -mx-6 -mt-6 px-6 py-3 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-slate-100">实时行情</h1>
            <span className="text-[10px] text-slate-600 hidden sm:inline">AI 量化实时数据支撑 · /api/market</span>
            {wsStatusBadge}
            {rt?.source && <span className="text-[10px] text-slate-600 font-mono">源:{rt.source}</span>}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-[#0a0e1a] border border-[#151d2e] rounded-lg p-0.5">
              {[3, 5, 10].map((s) => (
                <button
                  key={s}
                  onClick={() => setRefreshInterval(s)}
                  className={cn("px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors", refreshInterval === s ? "bg-cyan-500/20 text-cyan-400" : "text-slate-500 hover:text-slate-300")}
                >
                  {s}s
                </button>
              ))}
            </div>
            <button
              onClick={() => { loadSnapshot(); loadDetail(); loadSources(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#151d2e] text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
              刷新
              <span className="text-[10px] text-slate-600 ml-0.5 tabular-nums">{fmtCountdown(countdown)}</span>
            </button>
            {ws.status === "error" && (
              <button onClick={ws.retry} className="px-3 py-1.5 rounded-lg border border-red-500/30 text-xs text-red-400 hover:bg-red-500/10 transition-colors">
                重连
              </button>
            )}
          </div>
        </div>
      )}

      {loading && !rt && (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
        </div>
      )}

      {error && !rt && (
        <div className="p-8 text-center">
          <p className="text-red-400 text-sm mb-2">加载失败: {error}</p>
          <button onClick={() => { loadSnapshot(); loadDetail(); loadSources(); }} className="text-xs text-cyan-400 hover:underline">重试</button>
        </div>
      )}

      {rt && (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="xl:col-span-2 bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
                <CandlestickChart className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-bold text-slate-200">实时行情表</span>
                <span className="text-[10px] text-slate-600 ml-auto">点击行可查看 K线/资金流</span>
                {embedded && <span className="ml-2">{wsStatusBadge}</span>}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-[#0d1220] text-slate-500 sticky top-0">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">名称</th>
                      <th className="text-right px-3 py-2 font-medium">现价</th>
                      <th className="text-right px-3 py-2 font-medium">涨跌幅</th>
                      <th className="text-right px-3 py-2 font-medium hidden md:table-cell">成交量(万手)</th>
                      <th className="text-right px-3 py-2 font-medium hidden lg:table-cell">成交额</th>
                      <th className="text-right px-3 py-2 font-medium hidden lg:table-cell">换手</th>
                      <th className="text-right px-3 py-2 font-medium hidden xl:table-cell">PE</th>
                      <th className="text-right px-3 py-2 font-medium hidden xl:table-cell">总市值</th>
                      <th className="text-right px-3 py-2 font-medium hidden xl:table-cell">AI分</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#151d2e]">
                    {displayItems.map((it) => (
                      <RealtimeQuoteRow
                        key={it.quote.code}
                        code={it.quote.code}
                        name={it.quote.name}
                        price={it.quote.price}
                        changePct={it.quote.changePct}
                        volume={it.quote.volume}
                        amount={it.quote.amount}
                        turnover={it.quote.turnover}
                        pe={it.quote.pe}
                        totalMv={it.quote.totalMv}
                        score={it.aiScore.score}
                        selected={selected === it.quote.code}
                        onSelect={handleSelect}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="space-y-4">
              <AIScorePanel items={displayItems} onSelect={setSelected} />
              <SourceHealthCard sources={sources} />
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="xl:col-span-2 bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e] flex-wrap">
                <CandlestickChart className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-bold text-slate-200">K 线图</span>
                <span className="text-xs text-slate-300 font-medium">{selectedName}</span>
                <span className="text-[10px] text-slate-600 font-mono">{selected}</span>
                <div className="flex bg-[#0d1220] border border-[#151d2e] rounded-lg p-0.5 ml-auto">
                  {KLINE_PERIODS.map((p) => (
                    <button
                      key={p.key}
                      onClick={() => setPeriod(p.key)}
                      className={cn("px-2 py-1 rounded-md text-[10px] font-medium transition-colors", period === p.key ? "bg-cyan-500/20 text-cyan-400" : "text-slate-500 hover:text-slate-300")}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-2">
                <KlineChart bars={kline} period={period} />
              </div>
            </div>

            <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
                <DollarSign className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-bold text-slate-200">资金流</span>
                <span className="text-[10px] text-slate-600 ml-auto">{selectedName}</span>
              </div>
              <div className="p-2">
                {selectedItem?.capitalFlow && (
                  <div className="grid grid-cols-2 gap-2 px-2 py-2 border-b border-[#151d2e]">
                    <div>
                      <div className="text-[10px] text-slate-600">主力净流入</div>
                      <div className={cn("text-sm font-mono font-bold", selectedItem.capitalFlow.mainIn >= 0 ? "text-red-400" : "text-green-400")}>
                        {fmtFlow(selectedItem.capitalFlow.mainIn)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-600">5日主力</div>
                      <div className={cn("text-sm font-mono font-bold", selectedItem.capitalFlow.mainNetFlow5d >= 0 ? "text-red-400" : "text-green-400")}>
                        {fmtFlow(selectedItem.capitalFlow.mainNetFlow5d)}
                      </div>
                    </div>
                  </div>
                )}
                <CapitalFlowChart flow={capFlow} />
              </div>
            </div>
          </div>

          <p className="text-[10px] text-slate-700 text-center pt-2">
            数据更新: {rt.ts} · 实时价格由 WebSocket 推送 / 快照由 REST 每 {refreshInterval}s 刷新 · AI 评分为模型驱动结果，仅供研究参考，不构成投资建议
          </p>
        </>
      )}
    </div>
  );
}
