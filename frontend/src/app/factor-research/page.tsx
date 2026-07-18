"use client";

import { useState, useCallback, useEffect } from "react";
import { Boxes, Play, Loader2, Gauge, Activity, Layers, Radar, Trophy, TrendingUp, TrendingDown, Search, RefreshCw, BarChart4 } from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { cn, formatPct } from "@/lib/utils";
import {
  analyzeFactorCrossSection,
  type CrossSectionFactor,
  batchFactorScore,
  getFactorRanking,
  type FactorScoreResult,
  type BatchFactorScore,
} from "@/lib/api";
import { FactorRadar } from "@/components/charts/FactorRadar";

// ---- Tab 1: 单因子横截面 ----
const FACTORS = [
  { key: "momentum", label: "动量" },
  { key: "reversal", label: "反转" },
  { key: "idio_vol", label: "特质波动" },
  { key: "ma_conv", label: "均线收敛" },
  { key: "composite", label: "多因子复合" },
];
const INDICES = [
  { key: "sh000300", label: "沪深300" },
  { key: "sh000905", label: "中证500" },
];
const HORIZONS = [5, 10, 20, 60];
const SAMPLE_SIZES = [30, 50, 80];

// ---- Tab 2: 多因子评分 ----
const DIM_KEYS = [
  { key: "value", label: "估值", color: "#f59e0b" },
  { key: "quality", label: "质量", color: "#3b82f6" },
  { key: "momentum", label: "动量", color: "#8b5cf6" },
  { key: "volatility", label: "波动", color: "#ec4899" },
  { key: "sentiment", label: "情绪", color: "#10b981" },
];
const RANKING_DIMS = ["", "value", "quality", "momentum", "volatility", "sentiment"];
const RANKING_LABELS: Record<string, string> = {
  "": "综合总分", "value": "估值", "quality": "质量", "momentum": "动量",
  "volatility": "波动", "sentiment": "情绪",
};

export default function FactorResearchPage() {
  const [tab, setTab] = useState<"cross" | "multi" | "ic" | "returns">("multi");

  // ---- Tab 1 state ----
  const [loading1, setLoading1] = useState(false);
  const [csData, setCsData] = useState<CrossSectionFactor | null>(null);
  const [error1, setError1] = useState("");
  const [factor, setFactor] = useState("momentum");
  const [index, setIndex] = useState("sh000300");
  const [horizon, setHorizon] = useState(20);
  const [sampleSize, setSampleSize] = useState(50);

  // ---- Tab 2 state ----
  const [loading2, setLoading2] = useState(false);
  const [rankingData, setRankingData] = useState<BatchFactorScore | null>(null);
  const [error2, setError2] = useState("");
  const [rankingDim, setRankingDim] = useState("");
  const [selectedStock, setSelectedStock] = useState<FactorScoreResult | null>(null);
  const [stockCode, setStockCode] = useState("sh600519");

  // ---- Load ----
  useEffect(() => {
    if (tab === "multi" && !rankingData && !loading2) {
      loadRanking();
    }
  }, [tab]);

  const runCross = () => {
    setLoading1(true); setError1("");
    analyzeFactorCrossSection({ index, factor, horizon, sampleSize })
      .then(setCsData)
      .catch((e) => setError1(e instanceof Error ? e.message : "研究失败"))
      .finally(() => setLoading1(false));
  };

  const loadRanking = useCallback((dim?: string) => {
    setLoading2(true); setError2("");
    getFactorRanking(dim || undefined, 30)
      .then(setRankingData)
      .catch((e) => setError2(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading2(false));
  }, []);

  // ---- Tab 1 charts ----
  const icSeriesOption: EChartsOption = csData ? {
    backgroundColor: "transparent",
    grid: { top: 24, right: 16, bottom: 40, left: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    xAxis: { type: "category", data: csData.icSeries.map((d) => d.date), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 9, interval: Math.max(0, Math.floor(csData.icSeries.length / 8)) }, axisTick: { show: false } },
    yAxis: { type: "value", scale: true, axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 10 } },
    series: [{ type: "line", data: csData.icSeries.map((d) => ({ value: d.ic, coverage: d.coverage })), showSymbol: false, lineStyle: { color: "#f59e0b", width: 1 }, areaStyle: { color: "rgba(245,158,11,0.08)" }, markLine: { silent: true, symbol: "none", lineStyle: { color: "#475569", type: "dashed" }, data: [{ yAxis: 0 }] } }],
  } : {};

  const groupOption: EChartsOption = csData ? {
    backgroundColor: "transparent",
    grid: { top: 20, right: 16, bottom: 30, left: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    xAxis: { type: "category", data: csData.groups.map((g) => `Q${g.group}`), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 10 }, axisTick: { show: false } },
    yAxis: { type: "value", axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 10, formatter: "{value}%" } },
    series: [{ type: "bar", data: csData.groups.map((g) => ({ value: g.avgForwardReturn, cnt: g.count })), itemStyle: { borderRadius: [3, 3, 0, 0], color: (p: any) => (p.data.value >= 0 ? "rgba(52,211,153,0.75)" : "rgba(248,113,113,0.75)") }, barWidth: "55%" }],
  } : {};

  // ---- Tab 2 ranking bar chart ----
  const rankingChartOption: EChartsOption = rankingData ? {
    backgroundColor: "transparent",
    grid: { top: 10, right: 20, bottom: 30, left: 80 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 },
      formatter: (p: any) => {
        const d = Array.isArray(p) ? p[0] : p;
        const idx = d.dataIndex;
        const r = rankingData.results[idx];
        if (!r) return "";
        return `${r.name} (#${r.rank})<br/>综合: ${r.totalScore}<br/>估值:${r.dimensions.value.score} 质量:${r.dimensions.quality.score}<br/>动量:${r.dimensions.momentum.score} 波动:${r.dimensions.volatility.score} 情绪:${r.dimensions.sentiment.score}`;
      }
    },
    xAxis: { type: "value", max: 100, axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 10 }, splitLine: { lineStyle: { color: "#151d2e" } } },
    yAxis: { type: "category", data: rankingData.results.slice(0, 15).map((r) => `${r.name} (#${r.rank})`).reverse(), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#8b9dc3", fontSize: 10 }, axisTick: { show: false }, inverse: true },
    series: [{ type: "bar", data: rankingData.results.slice(0, 15).reverse().map((r) => r.totalScore), barWidth: "60%", itemStyle: { borderRadius: [0, 3, 3, 0],
      color: (p: any) => {
        const v = p.data;
        if (v >= 60) return "#22c55e"; if (v >= 45) return "#eab308"; return "#ef4444";
      }
    }, label: { show: true, position: "right", color: "#8b9dc3", fontSize: 10, formatter: "{c}" } }],
  } : {};

  // ---- Dimension heatmap (Tab 2) ----
  const dimHeatOption: EChartsOption = rankingData ? (() => {
    const top15 = rankingData.results.slice(0, 15);
    const data: [number, number, number][] = [];
    DIM_KEYS.forEach((dim, di) => {
      top15.forEach((r, ri) => {
        data.push([di, ri, r.dimensions[dim.key]?.score ?? 0]);
      });
    });
    return {
      backgroundColor: "transparent",
      grid: { top: 10, right: 20, bottom: 30, left: 70 },
      tooltip: { backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
      xAxis: { type: "category", data: DIM_KEYS.map((d) => d.label), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#8b9dc3", fontSize: 10 }, axisTick: { show: false }, position: "top" },
      yAxis: { type: "category", data: top15.map((r) => r.name).reverse(), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 9 }, axisTick: { show: false }, inverse: true },
      visualMap: { min: 0, max: 100, calculable: true, orient: "vertical", right: 4, bottom: 20, textStyle: { color: "#5a6a82", fontSize: 9 }, inRange: { color: ["#0b1a2e", "#1a3a5c", "#2d5a8e", "#4a90d9", "#6db3f2", "#a0d2ff"] } },
      series: [{ type: "heatmap", data: data.map((d) => [d[0], d[1] + 0.5, d[2]]), label: { show: true, color: "#e8edf5", fontSize: 8, formatter: "{c}" }, emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.5)" } } }],
    };
  })() : {};

  return (
    <div className="space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
            <Boxes className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">因子研究中心</h1>
            <p className="text-xs text-slate-500 mt-0.5">单因子横截面 + 多因子综合评分 + 全市场排名</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#0b0f19] p-1 rounded-lg border border-[#1e2a3d] w-fit">
        {["cross", "multi", "ic", "returns"].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t as typeof tab)}
            className={cn("px-4 py-1.5 text-sm rounded-md transition-colors",
              tab === t ? "bg-[#151d2e] text-slate-200 border border-[#2a3a54]" : "text-slate-500 hover:text-slate-300")}
          >
            {t === "cross" ? "单因子横截面" : t === "multi" ? "多因子综合评分" : t === "ic" ? "因子IC热力图" : "因子收益率"}
          </button>
        ))}
      </div>

      {/* ===== Tab: 单因子横截面 ===== */}
      {tab === "cross" && (
        <>
          <div className="card p-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div>
                <label className="text-xs text-slate-400 mb-1.5 block">股票池（指数成份股）</label>
                <div className="flex gap-1">
                  {INDICES.map((it) => (<button key={it.key} onClick={() => setIndex(it.key)} className={cn("flex-1 px-2 py-1.5 text-[11px] rounded border transition-colors", index === it.key ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : "border-[#1e2a3d] text-slate-500 hover:text-slate-300")}>{it.label}</button>))}
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1.5 block">因子</label>
                <div className="flex gap-1">
                  {FACTORS.map((f) => (<button key={f.key} onClick={() => setFactor(f.key)} className={cn("flex-1 px-2 py-1.5 text-[11px] rounded border transition-colors", factor === f.key ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : "border-[#1e2a3d] text-slate-500 hover:text-slate-300")}>{f.label}</button>))}
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1.5 block">预测周期（交易日）</label>
                <div className="flex gap-1">
                  {HORIZONS.map((h) => (<button key={h} onClick={() => setHorizon(h)} className={cn("flex-1 px-2 py-1.5 text-[11px] rounded border transition-colors", horizon === h ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : "border-[#1e2a3d] text-slate-500 hover:text-slate-300")}>{h}日</button>))}
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1.5 block">抽样数量</label>
                <div className="flex gap-1">
                  {SAMPLE_SIZES.map((s) => (<button key={s} onClick={() => setSampleSize(s)} className={cn("flex-1 px-2 py-1.5 text-[11px] rounded border transition-colors", sampleSize === s ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : "border-[#1e2a3d] text-slate-500 hover:text-slate-300")}>{s}</button>))}
                </div>
              </div>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <button onClick={runCross} disabled={loading1} className="btn-primary flex items-center gap-1.5">
                {loading1 ? <><Loader2 className="w-4 h-4 animate-spin" />研究中（约20-40s）…</> : <><Play className="w-4 h-4" />开始研究</>}
              </button>
              <span className="text-[10px] text-slate-600">首次拉取一篮子真实日K线较慢（已缓存10分钟），后续秒回。</span>
            </div>
          </div>

          {loading1 && <div className="card flex flex-col items-center justify-center h-60 text-slate-500"><Loader2 className="w-8 h-8 mb-3 animate-spin opacity-60" />正在并行拉取成份股真实日K线并计算横截面IC…</div>}
          {!loading1 && error1 && <div className="card p-4 text-rose-400 text-sm">研究失败：{error1}</div>}

          {!loading1 && csData && (<>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <KpiCard icon={<Gauge className="w-3.5 h-3.5" />} label="IC均值" value={csData.icMean.toFixed(4)} tone={csData.icMean >= 0 ? "pos" : "neg"} />
              <KpiCard icon={<Activity className="w-3.5 h-3.5" />} label="ICIR" value={csData.icir.toFixed(3)} tone={csData.icir >= 0 ? "pos" : "neg"} />
              <KpiCard icon={<Gauge className="w-3.5 h-3.5" />} label="IC胜率" value={`${csData.icWinRate}%`} tone={csData.icWinRate >= 50 ? "pos" : "neg"} />
              <KpiCard icon={<Layers className="w-3.5 h-3.5" />} label="多空收益" value={`${csData.longShortReturn >= 0 ? "+" : ""}${csData.longShortReturn.toFixed(2)}pp`} tone={csData.longShortReturn >= 0 ? "pos" : "neg"} />
              <KpiCard icon={<Boxes className="w-3.5 h-3.5" />} label="样本股票" value={`${csData.nStocks}`} />
              <KpiCard icon={<Activity className="w-3.5 h-3.5" />} label="有效交易日" value={`${csData.nDates}`} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <div className="card lg:col-span-2">
                <h2 className="text-sm font-semibold text-slate-200 mb-3">逐日跨截面IC时序</h2>
                <ReactECharts option={icSeriesOption} style={{ height: 280 }} notMerge />
              </div>
              <div className="card">
                <h2 className="text-sm font-semibold text-slate-200 mb-3">五分组平均未来收益</h2>
                <ReactECharts option={groupOption} style={{ height: 280 }} notMerge />
              </div>
            </div>
            {/* IC 分布直方图 */}
            <div className="card">
              <h2 className="text-sm font-semibold text-slate-200 mb-3">
                <BarChart4 className="w-4 h-4 inline mr-1.5 text-amber-400" />IC 分布直方图
              </h2>
              <ReactECharts
                option={(() => {
                  const ics = csData.icSeries.map((d) => d.ic);
                  const bins = 18;
                  const minIc = Math.min(...ics);
                  const maxIc = Math.max(...ics);
                  const range = maxIc - minIc || 0.02;
                  const binWidth = range / bins;
                  const histogram: number[] = Array(bins).fill(0);
                  const labels: string[] = [];
                  for (let i = 0; i < bins; i++) labels.push((minIc + i * binWidth).toFixed(3));
                  ics.forEach((v) => {
                    const idx = Math.min(Math.floor((v - minIc) / binWidth), bins - 1);
                    if (idx >= 0) histogram[idx]++;
                  });
                  return {
                    backgroundColor: "transparent",
                    grid: { top: 20, right: 20, bottom: 50, left: 40 },
                    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
                    xAxis: { type: "category", data: labels, axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 8, rotate: 50, interval: 2 }, axisTick: { show: false } },
                    yAxis: { type: "value", axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 10 }, name: "频次" },
                    series: [{
                      type: "bar",
                      data: histogram.map((v, i) => ({
                        value: v,
                        itemStyle: { color: parseFloat(labels[i]) >= 0 ? "rgba(52,211,153,0.7)" : "rgba(248,113,113,0.4)", borderRadius: [2, 2, 0, 0] },
                      })),
                      barWidth: "95%",
                      markLine: { silent: true, symbol: "none", lineStyle: { color: "#f59e0b", type: "dashed", width: 1.5 }, label: { color: "#f59e0b", fontSize: 10, formatter: "IC={c}" }, data: [{ xAxis: labels[Math.round(bins / 2)], name: "IC均值" }] },
                    }],
                  };
                })()}
                style={{ height: 250 }} notMerge
              />
            </div>
            <div className="card p-3 text-[11px] text-slate-500">{csData.note}</div>
          </>)}
        </>
      )}

      {/* ===== Tab: 多因子综合评分 ===== */}
      {tab === "multi" && (
        <>
          {/* Controls */}
          <div className="card p-4">
            <div className="flex items-center gap-3 flex-wrap">
              <label className="text-xs text-slate-400">排序维度：</label>
              {RANKING_DIMS.map((d) => (
                <button key={d || "total"} onClick={() => { setRankingDim(d); loadRanking(d || undefined); }}
                  className={cn("px-3 py-1.5 text-xs rounded border transition-colors", rankingDim === d ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : "border-[#1e2a3d] text-slate-500 hover:text-slate-300")}>
                  {RANKING_LABELS[d]}
                </button>
              ))}
              <button onClick={() => loadRanking(rankingDim || undefined)} className="btn-ghost flex items-center gap-1 text-xs ml-auto">
                <RefreshCw className="w-3.5 h-3.5" />刷新
              </button>
            </div>
          </div>

          {loading2 && <div className="card flex flex-col items-center justify-center h-60 text-slate-500"><Loader2 className="w-8 h-8 mb-3 animate-spin opacity-60" />正在并行拉取全市场数据并计算多因子评分…</div>}
          {!loading2 && error2 && <div className="card p-4 text-rose-400 text-sm">{error2}</div>}

          {!loading2 && rankingData && rankingData.results.length > 0 && (<>
            {/* Top 3 spotlight */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {rankingData.results.slice(0, 3).map((r, idx) => (
                <div key={r.code} onClick={() => setSelectedStock(r)} className={cn("card p-4 cursor-pointer border transition-all hover:border-amber-500/30",
                  idx === 0 ? "border-amber-500/50 bg-gradient-to-br from-amber-500/5 to-transparent" : "")}>
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <span className={cn("text-xs font-mono px-2 py-0.5 rounded", idx === 0 ? "bg-amber-500/20 text-amber-300" : "bg-slate-700/50 text-slate-400")}>#{r.rank}</span>
                      <span className="ml-2 text-sm font-semibold text-slate-200">{r.name}</span>
                    </div>
                    <span className="text-xs text-slate-500">{r.industry}</span>
                  </div>
                  <div className="text-3xl font-mono font-bold text-slate-100 mb-1">{r.totalScore}<span className="text-sm text-slate-500">/100</span></div>
                  <div className="text-xs text-slate-500 mb-3">百分位 {r.percentile}% · 截面 {r.universeSize} 只</div>
                  <div className="flex gap-1">
                    {DIM_KEYS.map((dk) => (
                      <div key={dk.key} className="flex-1 text-center">
                        <div className="text-[9px] text-slate-600 mb-0.5">{dk.label}</div>
                        <div className="text-xs font-mono" style={{ color: dk.color }}>{r.dimensions[dk.key]?.score ?? "-"}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Ranking bar chart + detail */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
              <div className="card lg:col-span-2">
                <h2 className="text-sm font-semibold text-slate-200 mb-3">Top 15 排名</h2>
                <ReactECharts option={rankingChartOption} style={{ height: 380 }} notMerge />
              </div>
              <div className="card lg:col-span-3">
                <h2 className="text-sm font-semibold text-slate-200 mb-3">
                  {selectedStock ? `${selectedStock.name} 五维评分` : "点选上方股票查看雷达图"}
                </h2>
                {selectedStock ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FactorRadar data={{
                      name: selectedStock.name,
                      totalScore: selectedStock.totalScore,
                      dimensions: DIM_KEYS.map((dk) => ({
                        label: dk.label,
                        score: selectedStock.dimensions[dk.key]?.score ?? 0,
                      })),
                    }} />
                    <div className="space-y-2">
                      {DIM_KEYS.map((dk) => (
                        <div key={dk.key}>
                          <div className="flex justify-between text-xs mb-1">
                            <span style={{ color: dk.color }}>{dk.label}</span>
                            <span className="font-mono text-slate-400">{selectedStock.dimensions[dk.key]?.score ?? "-"}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-slate-800">
                            <div className="h-full rounded-full transition-all" style={{ width: `${selectedStock.dimensions[dk.key]?.score ?? 0}%`, backgroundColor: dk.color }} />
                          </div>
                          {/* sub factors */}
                          <div className="flex gap-2 mt-1 flex-wrap">
                            {Object.entries(selectedStock.dimensions[dk.key]?.subFactors ?? {}).map(([sk, sv]) => (
                              <span key={sk} className="text-[9px] text-slate-600">{sk}: {typeof sv === 'number' ? sv.toFixed(0) : sv}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <FactorRadar data={{
                    name: "选择一只股票", totalScore: 0,
                    dimensions: DIM_KEYS.map((dk) => ({ label: dk.label, score: 0 })),
                  }} />
                )}
              </div>
            </div>

            {/* Full ranking table */}
            <div className="card overflow-x-auto">
              <h2 className="text-sm font-semibold text-slate-200 mb-3 px-4 pt-4">全截面排名（Top 30）</h2>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[#1e2a3d] text-slate-500">
                    <th className="text-left py-2 px-4 w-10">#</th>
                    <th className="text-left py-2 px-4">名称</th>
                    <th className="text-left py-2 px-4">行业</th>
                    <th className="text-right py-2 px-4">总分</th>
                    <th className="text-right py-2 px-4">百分位</th>
                    {DIM_KEYS.map((dk) => (
                      <th key={dk.key} className="text-right py-2 px-3" style={{ color: dk.color }}>{dk.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rankingData.results.slice(0, 30).map((r) => (
                    <tr key={r.code} onClick={() => setSelectedStock(r)} className={cn("border-b border-[#151d2e] hover:bg-[#151d2e] cursor-pointer transition-colors",
                      selectedStock?.code === r.code ? "bg-amber-500/5 border-amber-500/20" : "")}>
                      <td className="py-2 px-4 font-mono text-slate-500">{r.rank}</td>
                      <td className="py-2 px-4 text-slate-300">{r.name}</td>
                      <td className="py-2 px-4 text-slate-500">{r.industry}</td>
                      <td className="py-2 px-4 text-right font-mono font-semibold text-slate-200">{r.totalScore}</td>
                      <td className="py-2 px-4 text-right font-mono text-slate-500">{r.percentile}%</td>
                      {DIM_KEYS.map((dk) => (
                        <td key={dk.key} className="py-2 px-3 text-right font-mono text-slate-400">{r.dimensions[dk.key]?.score ?? "-"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-[10px] text-slate-700">基于westock quote/finance/kline真实数据，z-score截面标准化+CDF 0-100评分，五维等权。仅供量化研究参考。</p>
          </>)}
        </>
      )}

      {/* ===== Tab: IC热力图 ===== */}
      {tab === "ic" && (
        <>
          {!rankingData ? (
            <div className="card flex flex-col items-center justify-center h-60 text-slate-500">
              <p className="text-sm mb-2">请先在「多因子综合评分」Tab加载数据</p>
              <button onClick={() => { setTab("multi"); }} className="btn-ghost text-xs text-amber-400">跳转到多因子评分 →</button>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="card">
                <h2 className="text-sm font-semibold text-slate-200 mb-3 px-4 pt-4">Top 15 × 五维因子热力图</h2>
                <p className="text-[11px] text-slate-500 px-4 mb-2">颜色越亮代表该维度得分越高</p>
                <ReactECharts option={dimHeatOption} style={{ height: 400 }} notMerge />
              </div>
            </div>
          )}
        </>
      )}

      {/* ===== Tab: 因子收益率 & IC 分布 ===== */}
      {tab === "returns" && (
        <>
          {!csData && !rankingData ? (
            <div className="card flex flex-col items-center justify-center h-60 text-slate-500">
              <p className="text-sm mb-2">请先在「单因子横截面」或「多因子综合评分」Tab加载数据</p>
              <div className="flex gap-2">
                <button onClick={() => { setTab("cross"); }} className="btn-ghost text-xs text-amber-400">跳转到横截面研究 →</button>
                <button onClick={() => { setTab("multi"); }} className="btn-ghost text-xs text-cyan-400">跳转到多因子评分 →</button>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {/* IC 分布直方图 */}
              {csData && csData.icSeries.length > 0 && (
                <div className="card">
                  <h2 className="text-sm font-semibold text-slate-200 mb-3 px-4 pt-4">
                    <BarChart4 className="w-4 h-4 inline mr-1.5 text-amber-400" />
                    跨截面 IC 分布直方图
                  </h2>
                  <p className="text-[11px] text-slate-500 px-4 mb-2">
                    IC 均值 {csData.icMean.toFixed(4)} · 标准差 {csData.icStd.toFixed(4)} · ICIR {csData.icir.toFixed(3)} · 胜率 {csData.icWinRate}%
                  </p>
                  <ReactECharts
                    option={(() => {
                      const ics = csData.icSeries.map((d) => d.ic);
                      const bins = 20;
                      const minIc = Math.min(...ics);
                      const maxIc = Math.max(...ics);
                      const binWidth = (maxIc - minIc) / bins || 0.01;
                      const histogram: number[] = Array(bins).fill(0);
                      const labels: string[] = [];
                      for (let i = 0; i < bins; i++) {
                        labels.push((minIc + i * binWidth).toFixed(3));
                      }
                      ics.forEach((v) => {
                        const idx = Math.min(Math.floor((v - minIc) / binWidth), bins - 1);
                        if (idx >= 0) histogram[idx]++;
                      });
                      return {
                        backgroundColor: "transparent",
                        grid: { top: 20, right: 20, bottom: 40, left: 40 },
                        tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
                        xAxis: {
                          type: "category",
                          data: labels,
                          axisLine: { lineStyle: { color: "#1e2a3d" } },
                          axisLabel: { color: "#5a6a82", fontSize: 8, rotate: 45, interval: 3 },
                          axisTick: { show: false },
                          name: "IC 值",
                          nameTextStyle: { color: "#5a6a82", fontSize: 10 },
                        },
                        yAxis: { type: "value", axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 10 }, name: "频次", nameTextStyle: { color: "#5a6a82", fontSize: 10 } },
                        series: [{
                          type: "bar",
                          data: histogram.map((v, i) => ({
                            value: v,
                            itemStyle: {
                              color: parseFloat(labels[i]) >= 0
                                ? "rgba(52,211,153,0.7)"
                                : "rgba(248,113,113,0.5)",
                              borderRadius: [2, 2, 0, 0],
                            },
                          })),
                          barWidth: "90%",
                          markLine: {
                            silent: true, symbol: "none",
                            lineStyle: { color: "#f59e0b", type: "dashed", width: 1.5 },
                            label: { color: "#f59e0b", fontSize: 10, formatter: "均值 {c}" },
                            data: [{ xAxis: labels[Math.round(bins / 2)], name: "IC均值" }],
                          },
                        }],
                      };
                    })()}
                    style={{ height: 300 }}
                    notMerge
                  />
                </div>
              )}

              {/* 分组累计收益（pooling 模拟） */}
              {csData && csData.groups.length > 0 && (
                <div className="card">
                  <h2 className="text-sm font-semibold text-slate-200 mb-3 px-4 pt-4">
                    <TrendingUp className="w-4 h-4 inline mr-1.5 text-emerald-400" />
                    五分组平均收益 · 多空收益分解
                  </h2>
                  <p className="text-[11px] text-slate-500 px-4 mb-2">
                    多空收益（Q5 - Q1）= {csData.longShortReturn >= 0 ? "+" : ""}{csData.longShortReturn.toFixed(2)} pp · 因子 = {csData.factorLabel}
                  </p>
                  <ReactECharts
                    option={{
                      backgroundColor: "transparent",
                      grid: { top: 20, right: 16, bottom: 30, left: 40 },
                      tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
                      xAxis: { type: "category", data: csData.groups.map((g) => `Q${g.group}`), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#8b9dc3", fontSize: 11 }, axisTick: { show: false } },
                      yAxis: { type: "value", axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 10, formatter: "{value}%" }, name: "平均未来收益", nameTextStyle: { color: "#5a6a82", fontSize: 10 } },
                      series: [
                        {
                          type: "bar",
                          name: "平均收益",
                          data: csData.groups.map((g) => ({
                            value: g.avgForwardReturn,
                            cnt: g.count,
                          })),
                          barWidth: "50%",
                          itemStyle: {
                            borderRadius: [3, 3, 0, 0],
                            color: (p: any) => {
                              const colors = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6"];
                              return colors[p.dataIndex] || "#5a6a82";
                            },
                          },
                          label: { show: true, position: "top", color: "#8b9dc3", fontSize: 9, formatter: (p: any) => `${p.value >= 0 ? "+" : ""}${p.value.toFixed(2)}%` },
                        },
                        {
                          type: "line",
                          name: "趋势线",
                          data: csData.groups.map((g) => g.avgForwardReturn),
                          showSymbol: true,
                          symbolSize: 6,
                          lineStyle: { color: "#f59e0b", width: 2, type: "dashed" },
                          itemStyle: { color: "#f59e0b" },
                          z: 10,
                        },
                      ],
                    }}
                    style={{ height: 300 }}
                    notMerge
                  />
                </div>
              )}

              {/* 因子IC时序 + 滚动ICIR */}
              {csData && csData.icSeries.length > 0 && (
                <div className="card">
                  <h2 className="text-sm font-semibold text-slate-200 mb-3 px-4 pt-4">
                    <Activity className="w-4 h-4 inline mr-1.5 text-cyan-400" />
                    因子IC滚动IR · 预测力衰减分析
                  </h2>
                  <ReactECharts
                    option={(() => {
                      const rollingWindow = 20;
                      const icVals = csData.icSeries.map((d) => d.ic);
                      const rollingIR: number[] = [];
                      for (let i = 0; i < icVals.length; i++) {
                        if (i < rollingWindow - 1) { rollingIR.push(NaN); continue; }
                        const slice = icVals.slice(i - rollingWindow + 1, i + 1);
                        const mu = slice.reduce((a, b) => a + b, 0) / slice.length;
                        const sd = Math.sqrt(slice.reduce((s, v) => s + (v - mu) ** 2, 0) / slice.length) || 1e-8;
                        rollingIR.push(mu / sd);
                      }
                      return {
                        backgroundColor: "transparent",
                        grid: { top: 24, right: 60, bottom: 40, left: 40 },
                        tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
                        legend: { data: ["IC", "滚动ICIR (20日)"], bottom: 5, textStyle: { color: "#5a6a82", fontSize: 10 } },
                        xAxis: { type: "category", data: csData.icSeries.map((d) => d.date), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 8, interval: Math.max(0, Math.floor(csData.icSeries.length / 10)) }, axisTick: { show: false } },
                        yAxis: [
                          { type: "value", scale: true, axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 10 }, name: "IC", nameTextStyle: { color: "#5a6a82", fontSize: 10 } },
                          { type: "value", scale: true, axisLine: { show: false }, splitLine: { show: false }, axisLabel: { color: "#5a6a82", fontSize: 10 }, name: "ICIR", nameTextStyle: { color: "#5a6a82", fontSize: 10 } },
                        ],
                        series: [
                          { type: "bar", name: "IC", data: icVals.map((v) => ({ value: v, itemStyle: { color: v >= 0 ? "rgba(52,211,153,0.4)" : "rgba(248,113,113,0.3)" } })), barWidth: "70%" },
                          { type: "line", name: "滚动ICIR (20日)", yAxisIndex: 1, data: rollingIR, showSymbol: false, lineStyle: { color: "#f59e0b", width: 2 }, markLine: { silent: true, symbol: "none", lineStyle: { color: "#475569", type: "dashed" }, data: [{ yAxis: 0 }] } },
                        ],
                      };
                    })()}
                    style={{ height: 320 }}
                    notMerge
                  />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function KpiCard({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="card p-3">
      <div className="flex items-center gap-1 text-[10px] text-slate-500 mb-1">{icon}{label}</div>
      <div className={cn("font-mono font-bold text-sm", tone === "pos" ? "text-emerald-400" : tone === "neg" ? "text-rose-400" : "text-slate-200")}>{value}</div>
    </div>
  );
}
