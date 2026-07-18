"use client";

import { useMemo, useRef } from "react";
import {
  Download, Share2, FileText, TrendingUp, Activity, LineChart,
  Sigma, Gauge, Target, Trophy, AlertTriangle, Layers,
  Edit3, FlaskConical, Archive, Trash2,
} from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { cn, formatPct } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";
import { Modal } from "@/components/ui/Modal";
import type { StrategyCardData } from "@/components/ui/StrategyCard";

/* ============================================================
 * 确定性工具：保证报告在 SSR/CSR 一致，且同一策略每次生成稳定
 * ========================================================== */
function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function mulberry32(a: number) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function genCurve(seedStr: string, annual: number, n = 30): number[] {
  const rand = mulberry32(hashSeed(seedStr));
  const out: number[] = [];
  let prev = 100;
  const drift = annual / 100 / n;
  for (let i = 0; i < n; i++) {
    prev = Number((prev * (1 + drift) + (rand() - 0.5) * 6).toFixed(2));
    out.push(prev);
  }
  return out;
}
function computeDrawdown(curve: number[]): number[] {
  let peak = -Infinity;
  return curve.map((v) => {
    if (v > peak) peak = v;
    return Number((((v - peak) / peak) * 100).toFixed(2));
  });
}
function normalize(curve: number[]): number[] {
  if (!curve.length) return [];
  const base = curve[0];
  return curve.map((v) => Number(((v / base) * 100).toFixed(2)));
}

/* ============================================================
 * 策略类型 → 动态分析模块
 * ========================================================== */
const TYPE_META: Record<string, { icon: string; subtitle: string }> = {
  机器学习策略: { icon: "🤖", subtitle: "基于监督学习模型的多因子预测" },
  AI预测策略: { icon: "🔮", subtitle: "AI 模型生成的量价与情绪信号" },
  量化因子策略: { icon: "📊", subtitle: "多因子暴露与行业轮动配置" },
  事件驱动策略: { icon: "📅", subtitle: "财报/公告事件前后的异常收益" },
};

interface StrategyReportProps {
  strategy: StrategyCardData | null;
  open: boolean;
  onClose: () => void;
  onEdit?: (id: string) => void;
  onBacktest?: (id: string) => void;
  onArchive?: (id: string) => void;
  onDelete?: (id: string) => void;
}

export function StrategyReport({ strategy, open, onClose, onEdit, onBacktest, onArchive, onDelete }: StrategyReportProps) {
  const { toast } = useToast();
  const equityRef = useRef<any>(null);

  // 派生数据（strategy 为空时回落到空，避免 hook 报错）
  const data = useMemo(() => {
    if (!strategy) return null;
    const seed = strategy.id + strategy.name;
    const curve = strategy.equityCurve && strategy.equityCurve.length > 1
      ? strategy.equityCurve
      : genCurve(seed, strategy.annualizedReturn);
    const dd = computeDrawdown(curve);
    const norm = normalize(curve);
    const bench = normalize(genCurve("hs300-" + strategy.id, 6.5, curve.length));
    const totalReturn = curve.length > 1 ? ((curve[curve.length - 1] - curve[0]) / curve[0]) * 100 : 0;
    const calmar = strategy.maxDrawdown !== 0
      ? strategy.annualizedReturn / Math.abs(strategy.maxDrawdown)
      : 0;
    // 周期收益（用于分布/波动）
    const rets: number[] = [];
    for (let i = 1; i < curve.length; i++) rets.push((curve[i] - curve[i - 1]) / curve[i - 1]);
    const mean = rets.reduce((a, b) => a + b, 0) / (rets.length || 1);
    const variance = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / (rets.length || 1);
    const volatility = Math.sqrt(variance) * Math.sqrt(252) * 100; // 年化波动(%)
    return { curve, dd, norm, bench, totalReturn, calmar, volatility, rets };
  }, [strategy]);

  // 类型相关的确定性衍生（特征/信号/因子/事件）
  const dynamic = useMemo(() => {
    if (!strategy) return null;
    const rand = mulberry32(hashSeed(strategy.id + "::report"));
    const mk = (n: number) => Array.from({ length: n }, () => rand());

    if (strategy.type === "机器学习策略" || strategy.type === "AI预测策略") {
      const feats = ["动量因子", "波动率因子", "流动性因子", "情绪因子", "估值因子", "质量因子"];
      const raw = mk(feats.length).map((v) => 0.05 + v * 0.3);
      const sum = raw.reduce((a, b) => a + b, 0);
      const features = feats.map((f, i) => ({ name: f, importance: raw[i] / sum }));
      return { kind: "ml", features };
    }
    if (strategy.type === "量化因子策略") {
      const factors = ["规模", "价值", "动量", "质量", "低波", "成长"];
      const exposure = factors.map((f) => ({ name: f, value: Number((rand() * 2 - 1).toFixed(2)) }));
      return { kind: "factor", exposure };
    }
    if (strategy.type === "事件驱动策略") {
      const events = [
        { date: "T-20", name: "季报预披露", impact: 1 },
        { date: "T-12", name: "机构调研纪要", impact: 1 },
        { date: "T-5", name: "业绩预告超预期", impact: 2 },
        { date: "T+2", name: "龙虎榜净买入", impact: 1 },
        { date: "T+9", name: "分析师上调评级", impact: 2 },
      ].map((e) => ({ ...e, abn: Number(((rand() * 2 - 0.6) * (e.impact)).toFixed(2)) }));
      return { kind: "event", events };
    }
    return { kind: "generic" };
  }, [strategy]);

  if (!strategy || !data) {
    return null;
  }

  const s = strategy;
  const up = s.annualizedReturn >= 0;
  const lineColor = up ? "#34d399" : "#f87171";
  // 风险联动：基于回撤 + 夏普派生风险等级
  const rk = s.maxDrawdown >= 15 || (s.sharpeRatio ?? 99) < 2.0 ? "high" : s.maxDrawdown >= 10 || (s.sharpeRatio ?? 99) < 2.5 ? "mid" : "low";
  const rkMeta = {
    low: { t: "低风险", c: "text-emerald-400" },
    mid: { t: "中风险", c: "text-amber-400" },
    high: { t: "高风险", c: "text-rose-400" },
  }[rk];

  /* ---------- 图表 option ---------- */
  const equityOption: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 16, right: 16, bottom: 24, left: 44 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    xAxis: { type: "category", data: data.norm.map((_, i) => `D${i + 1}`), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 9 } },
    yAxis: { type: "value", scale: true, axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 9 } },
    series: [{
      type: "line", data: data.norm, smooth: true, symbol: "none",
      lineStyle: { color: lineColor, width: 2 },
      areaStyle: {
        color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: up ? "rgba(52,211,153,0.28)" : "rgba(248,113,113,0.28)" },
          { offset: 1, color: "rgba(52,211,153,0)" },
        ] },
      },
    }],
  };

  const ddOption: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 16, right: 16, bottom: 24, left: 44 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    xAxis: { type: "category", data: data.dd.map((_, i) => `D${i + 1}`), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { show: false } },
    yAxis: { type: "value", axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 9, formatter: "{value}%" } },
    series: [{ type: "line", data: data.dd, smooth: true, symbol: "none", lineStyle: { color: "#f87171", width: 1.5 }, areaStyle: { color: "rgba(248,113,113,0.15)" } }],
  };

  const cmpOption: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 30, right: 16, bottom: 24, left: 44 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    legend: { top: 0, textStyle: { color: "#8b9bb4", fontSize: 10 }, itemWidth: 14, itemHeight: 8 },
    xAxis: { type: "category", data: data.norm.map((_, i) => `D${i + 1}`), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { show: false } },
    yAxis: { type: "value", scale: true, axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 9 } },
    series: [
      { name: s.name.slice(0, 8), type: "line", data: data.norm, smooth: true, symbol: "none", lineStyle: { color: lineColor, width: 2 } },
      { name: "沪深300", type: "line", data: data.bench, smooth: true, symbol: "none", lineStyle: { color: "#64748b", width: 1.5, type: "dashed" } },
    ],
  };

  /* ---------- 操作：导出 / 分享 ---------- */
  const exportCSV = () => {
    const rows: string[] = [];
    rows.push("策略报告," + s.name);
    rows.push("策略类型," + s.type);
    rows.push("生成时间," + new Date().toLocaleString("zh-CN"));
    rows.push("");
    rows.push("指标,数值");
    rows.push("年化收益," + formatPct(s.annualizedReturn));
    rows.push("总收益率," + formatPct(data.totalReturn));
    rows.push("最大回撤," + formatPct(s.maxDrawdown, false));
    rows.push("夏普比率," + (s.sharpeRatio ?? "—"));
    rows.push("收益回撤比," + data.calmar.toFixed(2));
    rows.push("年化波动率," + data.volatility.toFixed(2) + "%");
    rows.push("胜率," + s.winRate + "%");
    rows.push("交易次数," + (s.tradesCount ?? 0));
    rows.push("当前盈亏," + (s.pnlAmount ?? "—"));
    rows.push("");
    rows.push("净值序列(起点=100)");
    data.norm.forEach((v, i) => rows.push(`D${i + 1},${v}`));
    const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `策略报告_${s.name}_${s.id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast("已导出 CSV 报告", "success");
  };

  const exportPNG = () => {
    const inst = equityRef.current?.getEchartsInstance?.();
    if (!inst) { toast("图表未就绪", "error"); return; }
    const url = inst.getDataURL({ pixelRatio: 2, backgroundColor: "#0f1626" });
    const a = document.createElement("a");
    a.href = url;
    a.download = `策略净值图_${s.name}.png`;
    a.click();
    toast("已导出净值图 PNG", "success");
  };

  const share = async () => {
    const text =
      `【AI策略报告】${s.name}（${s.type}）\n` +
      `年化收益 ${formatPct(s.annualizedReturn)} | 最大回撤 ${formatPct(s.maxDrawdown, false)} | ` +
      `夏普 ${s.sharpeRatio ?? "—"} | 胜率 ${s.winRate}%\n` +
      `查看：${typeof window !== "undefined" ? window.location.origin : ""}/strategies?report=${s.id}`;
    try {
      await navigator.clipboard.writeText(text);
      toast("报告摘要已复制到剪贴板", "success");
    } catch {
      toast("复制失败，请手动复制", "error");
    }
  };

  const kpis = [
    { icon: <TrendingUp className="w-3.5 h-3.5" />, label: "年化收益", value: formatPct(s.annualizedReturn), cls: up ? "pos" : "neg" },
    { icon: <Activity className="w-3.5 h-3.5" />, label: "总收益率", value: formatPct(data.totalReturn), cls: data.totalReturn >= 0 ? "pos" : "neg" },
    { icon: <AlertTriangle className="w-3.5 h-3.5" />, label: "最大回撤", value: formatPct(s.maxDrawdown, false), cls: "neg" },
    { icon: <Gauge className="w-3.5 h-3.5" />, label: "夏普比率", value: s.sharpeRatio != null ? s.sharpeRatio.toFixed(2) : "—", cls: "text-slate-200" },
    { icon: <Target className="w-3.5 h-3.5" />, label: "收益回撤比", value: data.calmar.toFixed(2), cls: data.calmar >= 1 ? "pos" : "text-slate-300" },
    { icon: <Sigma className="w-3.5 h-3.5" />, label: "年化波动", value: data.volatility.toFixed(1) + "%", cls: "text-slate-300" },
    { icon: <Trophy className="w-3.5 h-3.5" />, label: "胜率", value: s.winRate + "%", cls: s.winRate >= 50 ? "pos" : "neg" },
    { icon: <Layers className="w-3.5 h-3.5" />, label: "交易次数", value: String(s.tradesCount ?? 0), cls: "text-slate-300" },
  ];

  const meta = TYPE_META[s.type] ?? { icon: "📈", subtitle: "综合量化策略" };

  return (
    <Modal open={open} onClose={onClose} title={null} widthClass="max-w-4xl">
      {/* 报告头部 */}
      <div className="px-5 py-4 border-b border-[#1a2235] flex items-start justify-between gap-3 sticky top-0 bg-[#0f1626] z-10">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-500/20 to-violet-500/20 border border-cyan-500/20 flex items-center justify-center text-xl">
            {meta.icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-100">{s.name}</h2>
              <span className="badge badge-purple text-[9px]">{s.type}</span>
              <span className={cn("badge text-[9px]", rkMeta.c)}>{rkMeta.t}</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{meta.subtitle}</p>
            <p className="text-[10px] text-slate-600 mt-0.5">报告编号 {s.id} · 生成于 {new Date().toLocaleString("zh-CN")}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={exportCSV} className="btn-ghost text-[11px] flex items-center gap-1"><Download className="w-3.5 h-3.5" />数据</button>
          <button onClick={exportPNG} className="btn-ghost text-[11px] flex items-center gap-1"><FileText className="w-3.5 h-3.5" />图表</button>
          <button onClick={share} className="btn-primary text-[11px] flex items-center gap-1"><Share2 className="w-3.5 h-3.5" />分享</button>
        </div>
      </div>

      <div className="px-5 py-4 space-y-5">
        {/* 0) 策略描述 + 操作入口（合并原「详情」弹窗） */}
        <section className="card p-4 bg-[#0d1220]">
          <div className="flex items-center gap-1.5 mb-2">
            <FileText className="w-4 h-4 text-cyan-400" />
            <h3 className="section-title mb-0">策略描述</h3>
          </div>
          <p className="text-[12px] text-slate-300 leading-relaxed">{s.description || "（暂无策略描述）"}</p>
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            {onEdit && s.status !== "running" && (
              <button onClick={() => onEdit(s.id)} className="btn-ghost text-[11px] flex items-center gap-1"><Edit3 className="w-3.5 h-3.5" />编辑</button>
            )}
            {onBacktest && (
              <button onClick={() => onBacktest(s.id)} className="btn-ghost text-[11px] flex items-center gap-1"><FlaskConical className="w-3.5 h-3.5" />回测</button>
            )}
            {onArchive && s.status !== "archived" && (
              <button onClick={() => onArchive(s.id)} className="btn-ghost text-[11px] flex items-center gap-1"><Archive className="w-3.5 h-3.5" />归档</button>
            )}
            {onDelete && (
              <button onClick={() => onDelete(s.id)} className="btn-ghost text-[11px] flex items-center gap-1 text-rose-400"><Trash2 className="w-3.5 h-3.5" />删除</button>
            )}
          </div>
        </section>

        {/* 1) 关键数据摘要 */}
        <section>
          <h3 className="section-title mb-2.5 flex items-center gap-1.5"><Sigma className="w-4 h-4 text-cyan-400" />关键数据摘要</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {kpis.map((k) => (
              <div key={k.label} className="bg-[#0d1220] rounded-lg p-2.5 border border-[#1a2235]">
                <div className="flex items-center gap-1 text-[10px] text-slate-500 mb-1">{k.icon}{k.label}</div>
                <div className={cn("font-mono font-bold text-sm", k.cls)}>{k.value}</div>
              </div>
            ))}
          </div>
        </section>

        {/* 2) 图表化分析视图 */}
        <section>
          <h3 className="section-title mb-2.5 flex items-center gap-1.5"><LineChart className="w-4 h-4 text-cyan-400" />分析视图</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="card p-3">
              <div className="text-[11px] text-slate-400 mb-1">净值曲线（归一化，起点=100）</div>
              <ReactECharts ref={equityRef} option={equityOption} style={{ height: "200px", width: "100%" }} />
            </div>
            <div className="card p-3">
              <div className="text-[11px] text-slate-400 mb-1">回撤曲线（%）</div>
              <ReactECharts option={ddOption} style={{ height: "200px", width: "100%" }} />
            </div>
            <div className="card p-3 lg:col-span-2">
              <div className="text-[11px] text-slate-400 mb-1">策略 vs 沪深300 基准对比</div>
              <ReactECharts option={cmpOption} style={{ height: "220px", width: "100%" }} />
            </div>
          </div>
        </section>

        {/* 3) 按策略类型动态生成的分析模块 */}
        <section>
          <h3 className="section-title mb-2.5 flex items-center gap-1.5"><Activity className="w-4 h-4 text-cyan-400" />策略类型专项分析</h3>
          <div className="card p-4">
            {dynamic && dynamic.kind === "ml" && (
              <div>
                <div className="text-[11px] text-slate-400 mb-3">模型特征重要性（{s.type}）</div>
                <div className="space-y-2">
                  {(dynamic?.features ?? []).sort((a, b) => b.importance - a.importance).map((f) => (
                    <div key={f.name} className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-300 w-20">{f.name}</span>
                      <div className="flex-1 h-2 bg-[#0d1220] rounded overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-cyan-500 to-violet-500" style={{ width: `${(f.importance * 100).toFixed(1)}%` }} />
                      </div>
                      <span className="text-[10px] font-mono text-slate-400 w-12 text-right">{(f.importance * 100).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {dynamic && dynamic.kind === "factor" && (
              <div>
                <div className="text-[11px] text-slate-400 mb-3">因子暴露（正=超配，负=低配）</div>
                <div className="space-y-2">
                  {(dynamic?.exposure ?? []).map((f) => (
                    <div key={f.name} className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-300 w-12">{f.name}</span>
                      <div className="flex-1 flex items-center">
                        <div className="flex-1 h-2 bg-[#0d1220] rounded relative">
                          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[#2a3650]" />
                          <div
                            className={cn("h-full rounded", f.value >= 0 ? "bg-emerald-500" : "bg-rose-500")}
                            style={f.value >= 0
                              ? { marginLeft: "50%", width: `${Math.abs(f.value) * 50}%` }
                              : { marginRight: "50%", width: `${Math.abs(f.value) * 50}%` }}
                          />
                        </div>
                      </div>
                      <span className={cn("text-[10px] font-mono w-12 text-right", f.value >= 0 ? "pos" : "neg")}>{f.value > 0 ? "+" : ""}{f.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {dynamic && dynamic.kind === "event" && (
              <div>
                <div className="text-[11px] text-slate-400 mb-3">关键事件与异常收益（%）</div>
                <div className="space-y-2.5">
                  {(dynamic?.events ?? []).map((e, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-[10px] font-mono text-cyan-300 w-12">{e.date}</span>
                      <span className="text-[11px] text-slate-300 w-32">{e.name}</span>
                      <div className={cn("flex-1 h-1.5 rounded", e.abn >= 0 ? "bg-emerald-500/30" : "bg-rose-500/30")}>
                        <div className={cn("h-full rounded", e.abn >= 0 ? "bg-emerald-500" : "bg-rose-500")} style={{ width: `${Math.min(100, Math.abs(e.abn) * 40)}%` }} />
                      </div>
                      <span className={cn("text-[10px] font-mono w-12 text-right", e.abn >= 0 ? "pos" : "neg")}>{e.abn > 0 ? "+" : ""}{e.abn}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {dynamic?.kind === "generic" && (
              <div className="text-[11px] text-slate-500">该策略类型暂无专项分析模块，已展示通用绩效指标与图表。</div>
            )}
          </div>
        </section>

        <p className="text-[10px] text-slate-700 leading-relaxed">
          报告基于策略运行结果（净值曲线与绩效指标）自动生成，部分专项分析为模型派生示意。内容仅供量化研究参考，不构成投资建议。
        </p>
      </div>
    </Modal>
  );
}
