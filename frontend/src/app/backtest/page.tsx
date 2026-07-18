"use client";

import { useState } from "react";
import { FlaskConical, Play, Download, TrendingUp, Shield, Target, Clock, RefreshCw, GitCompare } from "lucide-react";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { MultiEquityCurveChart, type EquitySeries } from "@/components/charts/MultiEquityCurveChart";
import { strategies } from "@/lib/mock-data";
import { cn, formatPct } from "@/lib/utils";
import { runBacktest, type BacktestResult } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

const PALETTE = ["#3b82f6", "#f59e0b", "#34d399", "#a855f7", "#ef4444", "#22d3ee", "#ec4899", "#84cc16"];

export default function BacktestPage() {
  const [mode, setMode] = useState<"single" | "compare">("single");

  // 单策略
  const [running, setRunning] = useState(false);
  const [hasResult, setHasResult] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [dataSource, setDataSource] = useState<string>("");

  // 对比
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResults, setCompareResults] = useState<BacktestResult[]>([]);

  const { toast } = useToast();
  const [config, setConfig] = useState({
    strategy: strategies[0].name,
    startDate: "2024-01-01",
    endDate: "2026-07-10",
    stockPool: "沪深300",
    initialCapital: "1000000",
    code: "",
  });
  const [selected, setSelected] = useState<string[]>([
    "MA双均线交叉基准策略",
    "动量因子择时策略",
  ]);

  const toggleSelect = (name: string) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const baseConfig = () => ({
    startDate: config.startDate,
    endDate: config.endDate,
    stockPool: config.stockPool,
    initialCapital: Number(config.initialCapital),
    code: config.code.trim() || undefined,
  });

  const handleRun = () => {
    setRunning(true);
    setHasResult(false);
    runBacktest({ strategy: config.strategy, ...baseConfig() })
      .then((r) => {
        setResult(r);
        setDataSource(r.dataSource ?? "");
        setHasResult(true);
      })
      .catch(() => {})
      .finally(() => setRunning(false));
  };

  const handleCompare = () => {
    if (selected.length < 2) {
      toast("请至少选择 2 个策略进行对比", "error");
      return;
    }
    setCompareLoading(true);
    setCompareResults([]);
    Promise.all(selected.map((name) => runBacktest({ strategy: name, ...baseConfig() })))
      .then(setCompareResults)
      .catch(() => toast("对比回测失败", "error"))
      .finally(() => setCompareLoading(false));
  };

  const results = result
    ? {
        totalReturn: result.totalReturn,
        annualizedReturn: result.annualizedReturn,
        sharpeRatio: result.sharpeRatio,
        maxDrawdown: result.maxDrawdown,
        winRate: result.winRate,
        totalTrades: result.totalTrades,
        avgHoldDays: result.avgHoldDays,
      }
    : { totalReturn: 0, annualizedReturn: 0, sharpeRatio: 0, maxDrawdown: 0, winRate: 0, totalTrades: 0, avgHoldDays: 0 };

  // 导出回测结果为 CSV
  const exportResult = () => {
    if (!result) return;
    const header = "日期,代码,名称,方向,价格,数量,金额,盈亏\n";
    const rows = result.trades
      .map((t) =>
        [t.date, t.code, t.name, t.action === "buy" ? "买入" : "卖出", t.price.toFixed(2), t.shares, t.amount.toLocaleString(), t.pnl ?? ""].join(",")
      )
      .join("\n");
    const blob = new Blob(["\ufeff" + header + rows], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `回测结果_${result.symbol ?? result.strategyName}_${result.startDate}_${result.endDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast("回测结果已导出", "success");
  };

  // 对比模式的多线序列
  const compareSeries: EquitySeries[] = compareResults.map((r, i) => ({
    name: r.strategyName,
    color: PALETTE[i % PALETTE.length],
    points: r.equityCurve,
  }));

  return (
    <div className="space-y-5 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-200">回测系统</h1>
          <p className="text-sm text-slate-500 mt-0.5">历史数据回测 · 策略验证 · 参数优化 · 策略对比</p>
        </div>
        {dataSource === "westock" && <span className="badge badge-green">真实行情回测</span>}
      </div>

      {/* Mode toggle */}
      <div className="flex gap-1 w-fit">
        {([["single", "单策略回测"], ["compare", "策略对比"]] as const).map(([m, label]) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn("px-3 py-1.5 text-xs rounded-lg border transition-colors",
              mode === m ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-300" : "border-[#1e2a3d] text-slate-500 hover:text-slate-300")}
          >
            {m === "compare" && <GitCompare className="w-3.5 h-3.5 inline mr-1" />}
            {label}
          </button>
        ))}
      </div>

      {/* Config + Results */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        {/* Config Panel */}
        <div className="card lg:col-span-1">
          <h2 className="text-sm font-semibold text-slate-200 mb-4">回测参数</h2>
          <div className="space-y-4">
            {mode === "single" ? (
              <div>
                <label className="text-xs text-slate-400 mb-1.5 block">策略选择</label>
                <select
                  value={config.strategy}
                  onChange={(e) => setConfig({ ...config, strategy: e.target.value })}
                  className="w-full bg-[#0b0f19] border border-[#2a3142] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-600"
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.name}>{s.name}</option>
                  ))}
                </select>
              </div>
            ) : (
              <div>
                <label className="text-xs text-slate-400 mb-1.5 block">选择对比策略（≥2）</label>
                <div className="space-y-1 max-h-44 overflow-y-auto pr-1">
                  {strategies.map((s) => {
                    const on = selected.includes(s.name);
                    return (
                      <button
                        key={s.id}
                        onClick={() => toggleSelect(s.name)}
                        className={cn("w-full text-left px-2.5 py-1.5 text-xs rounded border transition-colors flex items-center gap-2",
                          on ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-200" : "border-[#1e2a3d] text-slate-500 hover:text-slate-300")}
                      >
                        <span className={cn("w-3 h-3 rounded-sm border flex-shrink-0", on ? "bg-cyan-400 border-cyan-400" : "border-[#334155]")} />
                        {s.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">开始日期</label>
              <input
                type="date"
                value={config.startDate}
                onChange={(e) => setConfig({ ...config, startDate: e.target.value })}
                className="w-full bg-[#0b0f19] border border-[#2a3142] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-600"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">结束日期</label>
              <input
                type="date"
                value={config.endDate}
                onChange={(e) => setConfig({ ...config, endDate: e.target.value })}
                className="w-full bg-[#0b0f19] border border-[#2a3142] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-600"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">股票池</label>
              <select
                value={config.stockPool}
                onChange={(e) => setConfig({ ...config, stockPool: e.target.value })}
                className="w-full bg-[#0b0f19] border border-[#2a3142] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-600"
              >
                {["沪深300", "中证500", "全部A股", "创业板", "自选股"].map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">标的代码（可选，如 600519）</label>
              <input
                value={config.code}
                onChange={(e) => setConfig({ ...config, code: e.target.value })}
                placeholder="留空则用股票池代表标的"
                className="w-full bg-[#0b0f19] border border-[#2a3142] rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">初始资金 (¥)</label>
              <input
                type="number"
                value={config.initialCapital}
                onChange={(e) => setConfig({ ...config, initialCapital: e.target.value })}
                className="w-full bg-[#0b0f19] border border-[#2a3142] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-600 font-mono"
              />
            </div>
            {mode === "single" ? (
              <button
                onClick={handleRun}
                disabled={running}
                className="btn-primary w-full flex items-center justify-center gap-1.5"
              >
                {running ? (
                  <>
                    <FlaskConical className="w-4 h-4 animate-spin" />
                    回测中...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    开始回测
                  </>
                )}
              </button>
            ) : (
              <button
                onClick={handleCompare}
                disabled={compareLoading}
                className="btn-primary w-full flex items-center justify-center gap-1.5"
              >
                {compareLoading ? (
                  <>
                    <FlaskConical className="w-4 h-4 animate-spin" />
                    对比回测中...
                  </>
                ) : (
                  <>
                    <GitCompare className="w-4 h-4" />
                    开始对比
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-3 space-y-5">
          {mode === "single" && (
            hasResult && result ? (
              <>
                {/* Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                  <ResultCard icon={<TrendingUp className="w-3.5 h-3.5" />} label="总收益" value={formatPct(results.totalReturn)} positive />
                  <ResultCard icon={<TrendingUp className="w-3.5 h-3.5" />} label="年化" value={formatPct(results.annualizedReturn)} positive />
                  <ResultCard icon={<Shield className="w-3.5 h-3.5" />} label="夏普" value={results.sharpeRatio.toString()} positive />
                  <ResultCard icon={<TrendingUp className="w-3.5 h-3.5 rotate-180" />} label="最大回撤" value={formatPct(results.maxDrawdown, false)} positive={false} />
                  <ResultCard icon={<Target className="w-3.5 h-3.5" />} label="胜率" value={`${results.winRate}%`} positive />
                  <ResultCard icon={<FlaskConical className="w-3.5 h-3.5" />} label="交易次数" value={results.totalTrades.toString()} />
                  <ResultCard icon={<Clock className="w-3.5 h-3.5" />} label="平均持仓" value={`${results.avgHoldDays}天`} />
                </div>

                {/* Equity Curve */}
                <div className="card">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h2 className="text-sm font-semibold text-slate-200">收益曲线</h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        标的 {result.symbol ?? result.strategyName} · {result.startDate} ~ {result.endDate}
                      </p>
                    </div>
                    <button onClick={exportResult} className="btn-secondary flex items-center gap-1.5 text-xs py-1">
                      <Download className="w-3 h-3" />
                      导出
                    </button>
                  </div>
                  <EquityCurveChart data={result.equityCurve} height={300} />
                </div>

                {/* Trade Records */}
                <div className="card">
                  <h2 className="text-sm font-semibold text-slate-200 mb-4">交易记录（{result.trades.length} 笔）</h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-slate-500 border-b border-[#2a3142]">
                          <th className="text-left py-2 pr-4 font-medium">日期</th>
                          <th className="text-left py-2 px-3 font-medium">代码/名称</th>
                          <th className="text-center py-2 px-3 font-medium">方向</th>
                          <th className="text-right py-2 px-3 font-medium">价格</th>
                          <th className="text-right py-2 px-3 font-medium">数量</th>
                          <th className="text-right py-2 px-3 font-medium">金额</th>
                          <th className="text-right py-2 px-3 font-medium">盈亏</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.trades.map((t, i) => (
                          <tr key={i} className="border-b border-[#1a1f2e] hover:bg-[#11161f]">
                            <td className="py-2.5 pr-4 font-mono text-xs text-slate-400">{t.date}</td>
                            <td className="px-3">
                              <span className="font-mono text-xs text-slate-500 mr-2">{t.code}</span>
                              <span className="text-slate-200 text-sm">{t.name}</span>
                            </td>
                            <td className="text-center px-3">
                              <span className={cn("badge", t.action === "buy" ? "badge-red" : "badge-green")}>
                                {t.action === "buy" ? "买入" : "卖出"}
                              </span>
                            </td>
                            <td className="text-right px-3 font-mono text-slate-300">{t.price.toFixed(2)}</td>
                            <td className="text-right px-3 font-mono text-slate-400">{t.shares}</td>
                            <td className="text-right px-3 font-mono text-slate-300">{t.amount.toLocaleString()}</td>
                            <td className="text-right px-3 font-mono">
                              {t.pnl != null ? (
                                <span className={t.pnl > 0 ? "text-green-400" : "text-red-400"}>
                                  {t.pnl > 0 ? "+" : ""}{t.pnl.toLocaleString()}
                                </span>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : !running && (
              <div className="card flex flex-col items-center justify-center h-96 text-slate-500">
                <RefreshCw className="w-8 h-8 mb-3 opacity-40" />
                配置参数后点击「开始回测」查看真实历史回测结果
              </div>
            )
          )}

          {mode === "compare" && (
            compareResults.length > 0 ? (
              <>
                <div className="card">
                  <h2 className="text-sm font-semibold text-slate-200 mb-3">策略净值对比</h2>
                  <MultiEquityCurveChart series={compareSeries} height={320} />
                </div>
                <div className="card">
                  <h2 className="text-sm font-semibold text-slate-200 mb-4">策略指标对比</h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-slate-500 border-b border-[#2a3142]">
                          <th className="text-left py-2 pr-4 font-medium">策略</th>
                          <th className="text-right py-2 px-3 font-medium">总收益</th>
                          <th className="text-right py-2 px-3 font-medium">年化</th>
                          <th className="text-right py-2 px-3 font-medium">夏普</th>
                          <th className="text-right py-2 px-3 font-medium">最大回撤</th>
                          <th className="text-right py-2 px-3 font-medium">胜率</th>
                          <th className="text-right py-2 px-3 font-medium">交易次数</th>
                          <th className="text-right py-2 px-3 font-medium">数据源</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compareResults.map((r, i) => (
                          <tr key={i} className="border-b border-[#1a1f2e] hover:bg-[#11161f]">
                            <td className="py-2.5 pr-4">
                              <span className="inline-flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-sm" style={{ background: PALETTE[i % PALETTE.length] }} />
                                <span className="text-slate-200 text-sm">{r.strategyName}</span>
                              </span>
                            </td>
                            <td className={cn("text-right px-3 font-mono", r.totalReturn >= 0 ? "text-emerald-400" : "text-rose-400")}>{formatPct(r.totalReturn)}</td>
                            <td className={cn("text-right px-3 font-mono", r.annualizedReturn >= 0 ? "text-emerald-400" : "text-rose-400")}>{formatPct(r.annualizedReturn)}</td>
                            <td className="text-right px-3 font-mono text-slate-300">{r.sharpeRatio}</td>
                            <td className="text-right px-3 font-mono text-rose-400">{formatPct(r.maxDrawdown, false)}</td>
                            <td className="text-right px-3 font-mono text-slate-300">{r.winRate}%</td>
                            <td className="text-right px-3 font-mono text-slate-400">{r.totalTrades}</td>
                            <td className="text-right px-3 font-mono text-slate-500">{r.dataSource ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-[10px] text-slate-600 mt-3">对比基于同一标的/区间的真实行情回测（westock）。因子择时策略严格防未来函数；非因子类策略默认按 MA 双均线交叉回测。</p>
                </div>
              </>
            ) : !compareLoading && (
              <div className="card flex flex-col items-center justify-center h-96 text-slate-500">
                <GitCompare className="w-8 h-8 mb-3 opacity-40" />
                左侧勾选 ≥2 个策略，点击「开始对比」查看净值叠加与指标对比
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

function ResultCard({
  icon,
  label,
  value,
  positive,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="card p-3">
      <div className="flex items-center gap-1 text-[10px] text-slate-500 mb-1">
        {icon}
        {label}
      </div>
      <div className={cn("font-mono font-bold text-sm", positive === true ? "text-green-400" : positive === false ? "text-red-400" : "text-slate-200")}>
        {value}
      </div>
    </div>
  );
}
