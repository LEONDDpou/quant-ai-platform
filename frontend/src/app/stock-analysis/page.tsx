"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Search, Brain, TrendingUp, DollarSign, Heart, Gauge, RefreshCw,
  Send, AlertTriangle, ThumbsUp, ThumbsDown, Eye, Loader2, Bot,
  Radar, Building2,
} from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { cn, formatPct, getColorClass } from "@/lib/utils";
import { API_BASE } from "@/lib/config";
import { fetchStockAnalysis, fetchStockKline, chatWithAI, predictWithAbuML, analyzeFactor, getFactorScore, getInstitutionAggregate, type StockAnalysis, type ChatMsg, type AbuMLPrediction, type FactorAnalysis, type FactorScoreResult, type InstitutionAggregate } from "@/lib/api";
import { FactorRadar } from "@/components/charts/FactorRadar";
import { SentimentGauge } from "@/components/ui/SentimentGauge";

type KlinePoint = { date: string; open: number; close: number; high: number; low: number; volume: number };

// 确定性 mock K 线（无后端时兜底，SSR/CSR 一致）
function genMockKline(seedStr: string, n = 60): KlinePoint[] {
  let seed = 0;
  for (const ch of seedStr) seed += ch.charCodeAt(0);
  const base0 = new Date("2025-01-01");
  const out: KlinePoint[] = [];
  let prev = 80 + (seed % 60);
  for (let i = 0; i < n; i++) {
    const r = Math.sin((i + 1) * 12.9898 + seed * 0.013) * 43758.5453;
    const rand = r - Math.floor(r);
    const o = prev;
    const c = Number((o + (rand - 0.5) * 6).toFixed(2));
    const hi = Number((Math.max(o, c) + rand * 3).toFixed(2));
    const lo = Number((Math.min(o, c) - rand * 3).toFixed(2));
    const vol = Math.floor(1000 + rand * 5000);
    const d = new Date(base0); d.setDate(d.getDate() + i);
    out.push({ date: `${d.getMonth() + 1}/${d.getDate()}`, open: o, close: c, high: hi, low: lo, volume: vol });
    prev = c;
  }
  return out;
}

// Mock 中信一级行业数据
const sectorETFs = [
  { name: "电子", value: "+1.84%", pos: true },
  { name: "食品饮料", value: "+0.42%", pos: true },
  { name: "银行", value: "-0.87%", pos: false },
  { name: "医药", value: "+1.55%", pos: true },
];

// Mock AI signals (A股)
const aiSignals = [
  { code: "600519.SH", dir: "看涨" as const, cls: "badge-bullish" as const },
  { code: "000858.SZ", dir: "震荡" as const, cls: "badge-neutral" as const },
  { code: "002594.SZ", dir: "看跌" as const, cls: "badge-bearish" as const },
];

// Mock market indicators (A股)
const marketIndicators = [
  { label: "沪深300", value: "3,452.1" },
  { label: "创业板指", value: "2,118.6" },
  { label: "科创50", value: "987.3" },
  { label: "十年国债", value: "2.28%" },
];

// Strategy recommendations
const strategyRecs = [
  {
    num: "①",
    title: "低波动因子轮动 — 风险评分 3/10",
    desc: "选取低波动率500只beta≤0.6的优质股票，利用行业轮动模型，预计年化12-16%",
    risk: "低",
    riskCls: "text-emerald-400",
  },
  {
    num: "②",
    title: "计算对冲策略 — 风险评分 4/70",
    desc: "利用行业间股价差异做套利，配对交易，市场中性，年化8-42%",
    risk: "低",
    riskCls: "text-emerald-400",
  },
  {
    num: "③",
    title: "量化趋势突破 — 风险评分 5/30",
    desc: "在趋势性上涨行情中捕捉突破信号，3/7D收益达5-8%年化",
    risk: "中",
    riskCls: "text-amber-400",
  },
  {
    num: "④",
    title: "期权覆盖增强 — 风险评级",
    desc: "推荐配置：50% 低波动轮动 + 35% 股指套利 + 15% 趋势追踪",
    risk: "中",
    riskCls: "text-amber-400",
  },
];

// Earnings calendar (A股)
const earningsCalendar = [
  { date: "08-26", company: "高优先级", stocks: ["600519.SH（年报）— 高端茅台酒放量，系列酒增速回升", "600036.SH（季报）— 零售转型提速，财富管理贡献提升"] },
  { date: "08-27", company: "次优先级", stocks: ["601318.SH（季报）— 寿险新业务价值改善，负债成本下行", "000333.SZ（中报）— 全球化+高端化双轮驱动"] },
  { date: "08-28", company: "规避建议", stocks: ["规避建议：财报披露前或存在波动风险，600519预期变动±8%，建议适当控制仓位"] },
];

// Picks (A股)
const highPicks = [
  { code: "600519.SH", reason: "高端白酒需求稳健+批价企稳回升", target: "¥1800-1950" },
  { code: "600036.SH", reason: "零售转型+财富管理贡献提升", target: "¥42-46" },
];
const secondaryPicks = [
  { code: "601318.SH", reason: "寿险NBV改善+负债成本下行", target: "" },
  { code: "000333.SZ", reason: "全球化和高端化双轮驱动", target: "" },
];

export default function StockAnalysisPage() {
  const [code, setCode] = useState("600519");
  const [searched, setSearched] = useState("600519");
  const [analysis, setAnalysis] = useState<StockAnalysis | null>(null);
  const [kline, setKline] = useState<KlinePoint[]>(genMockKline("600519"));
  const [period, setPeriod] = useState<"day" | "week" | "month">("day");
  const [loading, setLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [model, setModel] = useState("DeepSeek");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ABu ML 预测（移植自 bbfamily/abu）
  const [abuML, setAbuML] = useState<AbuMLPrediction | null>(null);
  const [abuLoading, setAbuLoading] = useState(false);
  const [abuHorizon, setAbuHorizon] = useState(5);

  const loadAbuML = (target = searched, h = abuHorizon) => {
    setAbuLoading(true);
    predictWithAbuML(target, h)
      .then(setAbuML)
      .catch(() => setAbuML(null))
      .finally(() => setAbuLoading(false));
  };

  useEffect(() => { loadAbuML(); }, [searched, abuHorizon]);

  // 因子分析（移植自 hugo2046/QuantsPlaybook）
  const [factor, setFactor] = useState<FactorAnalysis | null>(null);
  const [factorLoading, setFactorLoading] = useState(false);
  const [factorName, setFactorName] = useState("momentum");
  // 多因子评分
  const [mfScore, setMfScore] = useState<FactorScoreResult | null>(null);
  const [mfLoading, setMfLoading] = useState(false);

  const loadFactor = (target = searched, f = factorName) => {
    setFactorLoading(true);
    analyzeFactor(target, f, 20)
      .then(setFactor)
      .catch(() => setFactor(null))
      .finally(() => setFactorLoading(false));
  };

  // 机构聚合数据（v1.3.1 数据贯通）
  const [instData, setInstData] = useState<InstitutionAggregate | null>(null);
  const [instLoading, setInstLoading] = useState(false);

  useEffect(() => {
    setInstLoading(true);
    getInstitutionAggregate()
      .then(setInstData)
      .catch(() => setInstData(null))
      .finally(() => setInstLoading(false));
  }, []);

  // 多因子评分自动加载
  useEffect(() => {
    if (!searched) return;
    setMfLoading(true);
    getFactorScore(searched)
      .then(setMfScore)
      .catch(() => setMfScore(null))
      .finally(() => setMfLoading(false));
  }, [searched]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, chatLoading]);

  const sendMessage = async () => {
    const text = chatInput.trim();
    if (!text || chatLoading) return;
    setChatInput("");
    const next: ChatMsg[] = [...chatMessages, { role: "user", content: text }];
    setChatMessages(next);
    setChatLoading(true);
    try {
      const data = await chatWithAI(next, model);
      setChatMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "调用 AI 失败";
      setChatMessages((prev) => [...prev, { role: "assistant", content: `⚠️ ${msg}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  const load = (target = searched, p: "day" | "week" | "month" = "day") => {
    setLoading(true);
    fetchStockAnalysis(target)
      .then(async (a) => {
        setAnalysis(a);
        if (p === "day") setKline(a.klineData);
        else setKline(await fetchStockKline(target, p, 120));
      })
      .catch(() => { setKline(genMockKline(target)); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // 实时个股报价（轮询腾讯真实源，每 5s 一次，带状态机 + 重试）
  const [liveQuote, setLiveQuote] = useState<Record<string, any> | null>(null);
  const [liveStatus, setLiveStatus] = useState<"connecting" | "open" | "error">("connecting");
  const [liveError, setLiveError] = useState("");

  const fetchLiveQuote = useCallback(async (target = searched) => {
    if (!target) return;
    try {
      const r = await fetch(`${API_BASE}/api/paper/market/quote/${target}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const q = await r.json();
      setLiveQuote(q);
      setLiveStatus("open");
      setLiveError("");
    } catch (e) {
      setLiveStatus("error");
      setLiveError(e instanceof Error ? e.message : "请求失败");
    }
  }, [searched]);

  useEffect(() => {
    setLiveStatus("connecting");
    fetchLiveQuote();
    const id = setInterval(() => fetchLiveQuote(), 5000);
    return () => clearInterval(id);
  }, [searched, fetchLiveQuote]);

  const fmtVol = (v?: number) => {
    if (v == null) return "—";
    if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
    if (v >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
    return `${v}`;
  };

  // K-line chart option
  const klineOption: EChartsOption = {
    backgroundColor: "transparent",
    grid: [{ top: 20, right: 20, bottom: 80, left: 60 }, { top: 280, right: 20, bottom: 30, left: 60 }],
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    xAxis: [{ type: "category", data: kline.map((d) => d.date), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 9 }, axisTick: { show: false } },
      { type: "category", gridIndex: 1, data: kline.map((d) => d.date), axisLabel: { show: false } }],
    yAxis: [{ type: "value", scale: true, axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 10 } },
      { type: "value", gridIndex: 1, axisLine: { show: false }, splitLine: { show: false }, axisLabel: { color: "#5a6a82", fontSize: 10 } }],
    series: [
      { type: "candlestick", data: kline.map((d) => [d.open, d.close, d.low, d.high]), itemStyle: { color: "#34d399", color0: "#f87171", borderColor: "#34d399", borderColor0: "#f87171" } },
      { type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: kline.map((d) => d.volume), itemStyle: { color: (p: any) => (kline[p.dataIndex]?.close >= kline[p.dataIndex]?.open ? "rgba(52,211,153,0.3)" : "rgba(248,113,113,0.3)") } },
    ],
  };

  return (
    <div className="space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">AI诊股分析</h1>
            <p className="text-xs text-slate-500 mt-0.5">AI赋能 · 智能诊断 · 多维度评估输入</p>
          </div>
        </div>
        <div className="flex gap-1">
          {["DeepSeek", "通义", "沪深300"].map((btn) => (
            <button
              key={btn}
              onClick={() => setModel(btn)}
              className={cn(
                "px-2.5 py-1 text-[11px] font-medium rounded-md border transition-colors",
                model === btn
                  ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-300"
                  : "border-[#1e2a3d] text-slate-500 hover:text-slate-300 hover:bg-white/5"
              )}
            >{btn}</button>
          ))}
        </div>
      </div>

      {/* Main Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* ===== LEFT PANEL (3 cols) ===== */}
        <div className="lg:col-span-3 space-y-5">
          {/* Market Sentiment Gauge */}
          <div className="card p-4 flex flex-col items-center">
            <h3 className="section-title self-start mb-2">A股市场情绪</h3>
            <SentimentGauge score={68} size={140} />
          </div>

          {/* Sector ETF Data Table */}
          <div className="card p-4">
            <h3 className="section-title mb-2">关键数据概览<span className="badge badge-neutral text-[9px] ml-2">示例数据</span></h3>
            <table className="w-full text-xs">
              <tbody>
                {sectorETFs.map((etf) => (
                  <tr key={etf.name} className="border-b border-[#151d2e] last:border-0">
                    <td className="py-1.5 text-slate-400">{etf.name}</td>
                    <td className="py-1.5 text-right font-mono">{etf.value}</td>
                    <td className="py-1.5 w-8">
                      <span className={cn(etf.pos ? "pos" : "neg")}>
                        {etf.pos ? "↑" : "↓"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Today AI Signals */}
          <div className="card p-4">
            <h3 className="section-title mb-2">今日AI信号<span className="badge badge-neutral text-[9px] ml-2">示例数据</span></h3>
            <div className="space-y-1.5">
              {aiSignals.map((sig) => (
                <div key={sig.code} className="flex items-center justify-between py-1.5 bg-[#0d1220] rounded px-2">
                  <span className="font-mono text-xs text-slate-300">{sig.code}</span>
                  <span className={cn("badge text-[9px]", sig.cls)}>{sig.dir}</span>
                </div>
              ))}
            </div>
          </div>

          {/* ABu ML 预测（移植自 bbfamily/abu） */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-4 h-4 text-fuchsia-400" />
              <h3 className="section-title">ABu ML 预测</h3>
              <span className="badge badge-purple text-[9px] ml-auto">abu</span>
            </div>
            <p className="text-[10px] text-slate-600 mb-2">bbfamily/abu 风格特征 + 随机森林涨跌分类</p>

            <div className="flex gap-1 mb-3">
              {[5, 10, 20].map((h) => (
                <button
                  key={h}
                  onClick={() => setAbuHorizon(h)}
                  className={cn(
                    "px-2 py-0.5 text-[10px] rounded border transition-colors",
                    abuHorizon === h
                      ? "border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-300"
                      : "border-[#1e2a3d] text-slate-500 hover:text-slate-300"
                  )}
                >{h}日</button>
              ))}
            </div>

            {abuLoading ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-4">
                <Loader2 className="w-3 h-3 animate-spin" /> 训练中（约 10-15s）…
              </div>
            ) : abuML && abuML.direction !== "数据不足" ? (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">未来 {abuML.horizon} 日方向</span>
                  <span className={cn("badge text-[10px]", abuML.direction === "看涨" ? "badge-bullish" : "badge-bearish")}>
                    {abuML.direction}
                  </span>
                </div>
                <div>
                  <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                    <span>置信度</span>
                    <span className="font-mono text-slate-300">{(abuML.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-1.5 bg-[#0d1220] rounded overflow-hidden">
                    <div
                      className={cn("h-full", abuML.direction === "看涨" ? "bg-emerald-500" : "bg-rose-500")}
                      style={{ width: `${Math.round(abuML.confidence * 100)}%` }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-[#0d1220] rounded p-1.5">
                    <div className="text-[9px] text-slate-600">测试准确率</div>
                    <div className="text-xs font-mono text-slate-200">{(abuML.testAccuracy * 100).toFixed(1)}%</div>
                  </div>
                  <div className="bg-[#0d1220] rounded p-1.5">
                    <div className="text-[9px] text-slate-600">交叉验证</div>
                    <div className="text-xs font-mono text-slate-200">{(abuML.cvAccuracy * 100).toFixed(1)}%</div>
                  </div>
                  <div className="bg-[#0d1220] rounded p-1.5">
                    <div className="text-[9px] text-slate-600">样本数</div>
                    <div className="text-xs font-mono text-slate-200">{abuML.nSamples}</div>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 mb-1">关键特征贡献</div>
                  <div className="space-y-1">
                    {abuML.featureImportance.slice(0, 5).map((f) => (
                      <div key={f.feature} className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-slate-400 w-24 truncate">{f.feature}</span>
                        <div className="flex-1 h-1 bg-[#0d1220] rounded">
                          <div className="h-full bg-fuchsia-500/70" style={{ width: `${Math.round(f.importance * 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-slate-600 py-4">暂无可用的 ML 预测（数据不足或获取失败）。</div>
            )}
            <p className="text-[9px] text-slate-700 mt-2">模型胜率接近随机，仅供量化研究参考，不构成投资建议。</p>
          </div>

          {/* 因子分析（移植自 hugo2046/QuantsPlaybook） */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-1">
              <Gauge className="w-4 h-4 text-amber-400" />
              <h3 className="section-title">因子分析</h3>
              <span className="badge badge-yellow text-[9px] ml-auto">QP</span>
            </div>
            <p className="text-[10px] text-slate-600 mb-2">QuantsPlaybook 风格因子 · IC/ICIR/分组多空</p>

            <div className="flex gap-1 mb-3 flex-wrap">
              {[["momentum", "动量"], ["reversal", "反转"], ["idio_vol", "特质波动"], ["ma_conv", "均线收敛"]].map(([f, label]) => (
                <button
                  key={f}
                  onClick={() => setFactorName(f)}
                  className={cn(
                    "px-2 py-0.5 text-[10px] rounded border transition-colors",
                    factorName === f
                      ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                      : "border-[#1e2a3d] text-slate-500 hover:text-slate-300"
                  )}
                >{label}</button>
              ))}
            </div>

            {factorLoading ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-4">
                <Loader2 className="w-3 h-3 animate-spin" /> 因子计算中…
              </div>
            ) : factor && factor.nSamples > 0 ? (
              <div className="space-y-2.5">
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-[#0d1220] rounded p-1.5">
                    <div className="text-[9px] text-slate-600">IC</div>
                    <div className={cn("text-xs font-mono", factor.ic >= 0 ? "text-emerald-400" : "text-rose-400")}>
                      {factor.ic.toFixed(3)}
                    </div>
                  </div>
                  <div className="bg-[#0d1220] rounded p-1.5">
                    <div className="text-[9px] text-slate-600">ICIR</div>
                    <div className={cn("text-xs font-mono", factor.icir >= 0 ? "text-emerald-400" : "text-rose-400")}>
                      {factor.icir.toFixed(3)}
                    </div>
                  </div>
                  <div className="bg-[#0d1220] rounded p-1.5">
                    <div className="text-[9px] text-slate-600">IC胜率</div>
                    <div className="text-xs font-mono text-slate-200">{factor.icWinRate}%</div>
                  </div>
                </div>

                {/* 分组多空收益条 */}
                <div>
                  <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                    <span>五分组平均未来20日收益</span>
                    <span className="font-mono text-slate-300">
                      多空 {factor.longShortReturn >= 0 ? "+" : ""}{factor.longShortReturn.toFixed(2)}pp
                    </span>
                  </div>
                  <div className="flex items-end gap-1 h-16">
                    {factor.groups.map((g) => {
                      const v = g.avgForwardReturn;
                      const h = Math.min(100, Math.abs(v) * 6 + 4);
                      const isTop = g.group === Math.max(...factor.groups.map((x) => x.group));
                      const isBot = g.group === Math.min(...factor.groups.map((x) => x.group));
                      return (
                        <div key={g.group} className="flex-1 flex flex-col items-center justify-end h-full">
                          <span className="text-[8px] font-mono text-slate-500 mb-0.5">
                            {v >= 0 ? "+" : ""}{v.toFixed(1)}
                          </span>
                          <div
                            className={cn("w-full rounded-t", v >= 0 ? "bg-emerald-500/70" : "bg-rose-500/70", isTop && "ring-1 ring-amber-400", isBot && "ring-1 ring-slate-500")}
                            style={{ height: `${h}%` }}
                          />
                          <span className="text-[8px] text-slate-600 mt-0.5">Q{g.group}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="text-[10px] text-slate-400 bg-[#0d1220] rounded p-2 leading-relaxed">
                  <span className="text-slate-500">最新信号：</span>{factor.latestSignal}
                </div>
                <div className="text-[9px] text-slate-700">
                  样本 {factor.nSamples} · {factor.startDate} ~ {factor.endDate}
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-slate-600 py-4">暂无可用的因子分析（数据不足或获取失败）。</div>
            )}
            <p className="text-[9px] text-slate-700 mt-2">因子评价基于真实日K线，结果仅供量化研究参考，不构成投资建议。</p>
          </div>

          {/* 多因子综合评分 */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-1">
              <Radar className="w-4 h-4 text-blue-400" />
              <h3 className="section-title">多因子综合评分</h3>
              <span className="badge badge-blue text-[9px] ml-auto">v1.0</span>
            </div>
            <p className="text-[10px] text-slate-600 mb-2">五维因子模型 · 估值/质量/动量/波动/情绪</p>

            {mfLoading ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-4">
                <Loader2 className="w-3 h-3 animate-spin" /> 因子计算中（约10-20s）…
              </div>
            ) : mfScore && mfScore.totalScore > 0 ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="text-3xl font-mono font-bold text-slate-100">{mfScore.totalScore}<span className="text-sm text-slate-500">/100</span></div>
                  <div className="text-xs text-slate-500">
                    <div>全市场排名 <span className="font-mono text-slate-300">#{mfScore.rank}/{mfScore.universeSize}</span></div>
                    <div>超越 <span className="font-mono text-amber-400">{mfScore.percentile}%</span> 股票</div>
                  </div>
                </div>
                <div className="h-[220px]">
                  <FactorRadar data={{
                    name: mfScore.name,
                    totalScore: mfScore.totalScore,
                    dimensions: [
                      { label: "估值", score: mfScore.dimensions.value?.score ?? 0 },
                      { label: "质量", score: mfScore.dimensions.quality?.score ?? 0 },
                      { label: "动量", score: mfScore.dimensions.momentum?.score ?? 0 },
                      { label: "波动", score: mfScore.dimensions.volatility?.score ?? 0 },
                      { label: "情绪", score: mfScore.dimensions.sentiment?.score ?? 0 },
                    ],
                  }} />
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-slate-600 py-4">暂无可用的多因子评分（数据不足或获取失败）。</div>
            )}
            <p className="text-[9px] text-slate-700 mt-2">基于westock真实数据，z-score截面标准化+CDF 0-100评分。仅供量化研究参考。</p>
          </div>

          {/* 机构动向快览（v1.3.1 数据贯通） */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-1">
              <Building2 className="w-4 h-4 text-fuchsia-400" />
              <h3 className="section-title">机构动向快览</h3>
              <span className="badge badge-purple text-[9px] ml-auto">v1.3.1</span>
            </div>
            <p className="text-[10px] text-slate-600 mb-2">龙虎榜 · 北向 · 活跃度实时聚合</p>
            {instLoading ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-4">
                <Loader2 className="w-3 h-3 animate-spin" /> 加载中…
              </div>
            ) : instData ? (
              <div className="space-y-2.5">
                {/* 活跃度条 */}
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">机构活跃度</span>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-2 bg-[#0d1220] rounded overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded",
                          (instData.institutionActivity?.score ?? 0) >= 60
                            ? "bg-emerald-500"
                            : (instData.institutionActivity?.score ?? 0) >= 30
                              ? "bg-amber-500"
                              : "bg-slate-600",
                        )}
                        style={{ width: `${instData.institutionActivity?.score ?? 0}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-slate-300">
                      {instData.institutionActivity?.score ?? 0}
                    </span>
                  </div>
                </div>
                {/* 北向资金 */}
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">北向资金</span>
                  <span
                    className={cn(
                      "text-xs font-mono font-medium",
                      (instData.northbound?.today ?? 0) > 0
                        ? "text-red-400"
                        : (instData.northbound?.today ?? 0) < 0
                          ? "text-green-400"
                          : "text-slate-500",
                    )}
                  >
                    {instData.northbound?.todayDesc ?? "—"}
                  </span>
                </div>
                {/* 主力方向 */}
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">主力方向</span>
                  <span
                    className={cn(
                      "badge text-[9px]",
                      instData.institutionActivity?.mainDirection === "流入"
                        ? "badge-green"
                        : "badge-red",
                    )}
                  >
                    {instData.institutionActivity?.mainDirection ?? "—"}
                  </span>
                </div>
                {/* 龙虎榜Top3 */}
                <div className="pt-2 border-t border-[#151d2e]">
                  <div className="text-[10px] text-slate-600 mb-1">龙虎榜净买入 TOP3</div>
                  <div className="space-y-0.5">
                    {(instData.lhb || []).slice(0, 3).map((e) => (
                      <div key={e.code} className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-400 truncate max-w-[80px]">{e.name}</span>
                        <span className="font-mono text-red-400">{e.netBuyAmt}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <p className="text-[9px] text-slate-700">
                  更新于 {instData.timestamp}
                </p>
              </div>
            ) : (
              <div className="text-[11px] text-slate-600 py-4">暂无可用的机构数据。</div>
            )}
          </div>

          {/* Market Indicators */}
          <div className="card p-4">
            <h3 className="section-title mb-2">市场关键指标<span className="badge badge-neutral text-[9px] ml-2">示例数据</span></h3>
            <div className="space-y-1.5">
              {marketIndicators.map((ind) => (
                <div key={ind.label} className="flex justify-between py-1 border-b border-[#151d2e] last:border-0">
                  <span className="text-[11px] text-slate-500">{ind.label}</span>
                  <span className="font-mono text-xs text-slate-300">{ind.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ===== CENTER PANEL (9 cols) ===== */}
        <div className="lg:col-span-9 space-y-5">
          {/* 实时个股报价（腾讯真实源，5s 自动刷新，含加载/异常/重试） */}
          <div className="card p-4">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-slate-100 truncate">
                    {liveQuote?.name ?? (searched || "—")}
                  </span>
                  <span className="font-mono text-xs text-slate-500">{searched}</span>
                </div>
                {liveStatus === "open" && liveQuote ? (
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <span className={cn("text-2xl font-mono font-bold", getColorClass(liveQuote.changePct ?? 0))}>
                      {(liveQuote.price ?? 0).toFixed(2)}
                    </span>
                    <span className={cn("font-mono text-sm", getColorClass(liveQuote.changePct ?? 0))}>
                      {liveQuote.changePct >= 0 ? "+" : ""}{(liveQuote.changePct ?? 0).toFixed(2)}%
                    </span>
                    <span className="text-xs text-slate-500">成交量 {fmtVol(liveQuote.volume)}</span>
                    <span className={cn("badge text-[9px]", liveQuote.dataSource === "tencent" ? "badge-green" : "badge-neutral")}>
                      {liveQuote.dataSource === "tencent" ? "实时·腾讯" : "模拟"}
                    </span>
                  </div>
                ) : liveStatus === "connecting" ? (
                  <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                    <Loader2 className="w-3 h-3 animate-spin" /> 实时行情连接中…
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-xs text-amber-300 mt-1">
                    <AlertTriangle className="w-3 h-3" /> 实时行情获取失败：{liveError}
                    <button onClick={() => fetchLiveQuote()} className="badge badge-yellow text-[9px] cursor-pointer">重试</button>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-600 ml-auto">每 5 秒自动刷新</span>
            </div>
          </div>
          {/* Tabbed Analysis Content */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-4">
              <Eye className="w-4 h-4 text-cyan-400" />
              <span className="section-title">针对当前A股市场环境，推荐以下低波动量化策略组合：</span>
            </div>

            {/* Strategy Recommendations */}
            <div className="space-y-3">
              {strategyRecs.map((rec) => (
                <div key={rec.num} className="bg-[#0d1220] rounded-lg p-3 border border-[#1a2235]">
                  <div className="flex items-start gap-2">
                    <span className="text-sm font-bold text-cyan-400 flex-shrink-0 mt-0.5">{rec.num}</span>
                    <div className="min-w-0">
                      <h4 className="text-sm font-semibold text-slate-200">{rec.title.split("—")[0]}</h4>
                      <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{rec.desc}</p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <span className="text-[10px] text-slate-500">风险评级：</span>
                        <span className={cn("badge text-[9px]", rec.risk === "低" ? "badge-green" : rec.risk === "中" ? "badge-yellow" : "badge-red")}>{rec.risk}</span>
                        <span className={cn("text-[10px] font-mono ml-auto", rec.riskCls)}>
                          {rec.title.match(/评分\s*(\S+)/)?.[1]}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Earnings Calendar */}
            <div className="mt-4 pt-4 border-t border-[#1e2a3d]">
              <h3 className="section-title mb-2 flex items-center gap-1">
                下周财报日历重点关注
                <span className="text-[10px] text-slate-600 font-normal">(按重要性排序)</span>
              </h3>
              <div className="space-y-3">
                {earningsCalendar.map((ev) => (
                  <div key={ev.date} className="bg-[#0d1220] rounded-lg p-3 border border-[#1a2235]">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="badge badge-blue text-[10px]">{ev.date}</span>
                      <span className={cn("badge text-[10px]",
                        ev.company.includes("高") ? "badge-green" : ev.company.includes("次") ? "badge-yellow" : "badge-red"
                      )}>{ev.company}</span>
                    </div>
                    <ul className="list-disc list-inside space-y-1">
                      {ev.stocks.map((stock, i) => (
                        <li key={i} className="text-xs text-slate-400 leading-relaxed">{stock}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            {/* Stock Picks */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 pt-4 border-t border-[#1e2a3d]">
              <div>
                <h4 className="text-xs font-semibold text-emerald-400 mb-2">高优先级</h4>
                <div className="space-y-1.5">
                  {highPicks.map((pick) => (
                    <div key={pick.code} className="flex items-center justify-between py-1.5 px-2 bg-emerald-500/5 rounded border border-emerald-500/10">
                      <div>
                        <span className="font-mono text-xs text-emerald-400 font-medium">{pick.code}</span>
                        <span className="text-[10px] text-slate-500 ml-1">({pick.target})</span>
                      </div>
                      <span className="text-[10px] text-slate-400 max-w-[180px] truncate">{pick.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-amber-400 mb-2">次优先级</h4>
                <div className="space-y-1.5">
                  {secondaryPicks.map((pick) => (
                    <div key={pick.code} className="flex items-center justify-between py-1.5 px-2 bg-amber-500/5 rounded border border-amber-500/10">
                      <span className="font-mono text-xs text-amber-400 font-medium">{pick.code}</span>
                      <span className="text-[10px] text-slate-400 max-w-[180px] truncate">{pick.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* AI 投研助手聊天框 */}
          <div className="card p-4 flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <Bot className="w-4 h-4 text-cyan-400" />
              <span className="section-title">AI 投研助手</span>
              <span className="badge badge-purple text-[9px] ml-auto">{model}</span>
            </div>

            <div className="h-[280px] overflow-y-auto space-y-3 mb-3 pr-1">
              {chatMessages.length === 0 ? (
                <div className="text-xs text-slate-600 text-center mt-20 px-4 leading-relaxed">
                  向 AI 助手提问，例如：<br />「分析 600519 的量化信号与估值逻辑」
                </div>
              ) : (
                chatMessages.map((m, i) => (
                  <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                    <div className={cn(
                      "max-w-[82%] rounded-lg px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap break-words",
                      m.role === "user"
                        ? "bg-cyan-500/15 text-cyan-100"
                        : "bg-[#0d1220] text-slate-300 border border-[#1a2235]"
                    )}>
                      {m.content}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-[#0d1220] border border-[#1a2235] rounded-lg px-3 py-2 text-xs text-slate-500 flex items-center gap-2">
                    <Loader2 className="w-3 h-3 animate-spin" /> 思考中…
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="flex items-center gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="输入您的问题… 例如：分析600519财报超预期的量化信号"
                className="input-dark flex-1"
                onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              />
              <button
                className="btn-primary px-3 disabled:opacity-50"
                onClick={sendMessage}
                disabled={chatLoading || !chatInput.trim()}
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-[10px] text-slate-700 mt-2">AI 助手内容由大模型生成，仅作参考，不构成投资建议。请交叉多方信息后独立判断。</p>
          </div>
        </div>
      </div>
    </div>
  );
}
