"use client";

import { useState, useCallback } from "react";
import {
  Radar,
  Play,
  Loader2,
  Search,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Lightbulb,
  BarChart3,
  Target,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { cn, formatPct, formatCurrency } from "@/lib/utils";
import {
  screenStocks,
  analyzeSelection,
  runPickerReport,
  type StockCandidate,
  type ScreenResult,
  type AnalyzeResult,
  type ReportResult,
} from "@/lib/api";

// ─── 市场预设 ───────────────────────────────────────
const MARKETS = [
  { key: "a", label: "A 股" },
  { key: "hk", label: "港股" },
  { key: "us", label: "美股" },
];

const PRESET_EXPRESSIONS: Record<string, string> = {
  a: "intersect([PE_TTM > 0, PE_TTM < 15, ROETTM > 15])",
  hk: "intersect([PE_TTM > 0, PE_TTM < 12, ROETTM > 12])",
  us: "intersect([PE_TTM > 0, PE_TTM < 20, ROETTM > 12])",
};

// ─── 选股状态 ───────────────────────────────────────
type Phase = "idle" | "screening" | "analyzing" | "reporting" | "done";

export default function StockPickerPage() {
  // 表单
  const [market, setMarket] = useState("a");
  const [expression, setExpression] = useState(PRESET_EXPRESSIONS["a"]);
  const [limit, setLimit] = useState(15);

  // 结果
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [screenResult, setScreenResult] = useState<ScreenResult | null>(null);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null);
  const [reportResult, setReportResult] = useState<ReportResult | null>(null);

  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());

  // ── 切换市场时更新预设表达式 ──
  const changeMarket = (m: string) => {
    setMarket(m);
    setExpression(PRESET_EXPRESSIONS[m] ?? "");
    setScreenResult(null);
    setAnalyzeResult(null);
    setReportResult(null);
    setPhase("idle");
    setError("");
    setSelectedCodes(new Set());
  };

  // ── Step 1: 条件选股 ──
  const doScreen = useCallback(() => {
    if (!expression.trim()) {
      setError("请输入选股表达式");
      return;
    }
    setPhase("screening");
    setError("");
    setAnalyzeResult(null);
    setReportResult(null);
    setSelectedCodes(new Set());

    screenStocks({ market, expression, limit })
      .then((res) => {
        setScreenResult(res);
        setPhase("idle");
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "选股失败");
        setPhase("idle");
      });
  }, [market, expression, limit]);

  // ── Step 2: AI 选股逻辑分析 ──
  const doAnalyze = useCallback(() => {
    if (!screenResult?.candidates.length) return;
    setPhase("analyzing");
    setError("");
    analyzeSelection({
      market,
      expression,
      candidates: screenResult.candidates,
    })
      .then((res) => {
        setAnalyzeResult(res);
        setPhase("idle");
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "分析失败");
        setPhase("idle");
      });
  }, [market, expression, screenResult]);

  // ── Step 3: 回测报告 ──
  const doReport = useCallback(() => {
    const codes = selectedCodes.size > 0
      ? Array.from(selectedCodes)
      : screenResult?.candidates.map((c) => c.code) ?? [];
    if (!codes.length) {
      setError("请先筛选股票或勾选股票");
      return;
    }
    setPhase("reporting");
    setError("");
    runPickerReport({ codes })
      .then((res) => {
        setReportResult(res);
        setPhase("done");
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "回测失败");
        setPhase("idle");
      });
  }, [selectedCodes, screenResult]);

  // ── 切换选中 ──
  const toggleCode = (code: string) => {
    setSelectedCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code); else next.add(code);
      return next;
    });
  };
  const selectAll = () => {
    if (!screenResult) return;
    setSelectedCodes(new Set(screenResult.candidates.map((c) => c.code)));
  };
  const deselectAll = () => setSelectedCodes(new Set());

  const busy = phase !== "idle" && phase !== "done";

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-6xl mx-auto p-6 space-y-5">
        {/* 页面标题 */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
            <Radar className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100">智能选股</h1>
            <p className="text-xs text-slate-500">AI 辅助条件选股 + 回测验证 + 成败归因</p>
          </div>
        </div>

        {/* ── 模块 1+5: 市场切换 + 条件筛选 + 结果列表 ── */}
        <Card>
          <CardHeader icon={<Search className="w-4 h-4" />} title="条件筛选" badge="模块 1" />

          {/* 市场切换 */}
          <div className="flex gap-1.5 mb-4">
            {MARKETS.map((m) => (
              <button
                key={m.key}
                onClick={() => changeMarket(m.key)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  market === m.key
                    ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    : "bg-[#0d1220] text-slate-400 border border-[#1a2235] hover:border-amber-500/20 hover:text-slate-300",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* 表达式输入 */}
          <div className="flex gap-2 mb-3">
            <input
              value={expression}
              onChange={(e) => setExpression(e.target.value)}
              placeholder="输入 westock-tool 选股表达式…"
              className="flex-1 bg-[#0d1220] border border-[#1e2a3d] rounded-lg px-3 py-2 text-xs text-slate-200 font-mono placeholder:text-slate-600 focus:outline-none focus:border-amber-500/50"
            />
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="bg-[#0d1220] border border-[#1e2a3d] rounded-lg px-2 py-2 text-xs text-slate-300 focus:outline-none focus:border-amber-500/50"
            >
              {[5, 10, 15, 20, 30].map((n) => (
                <option key={n} value={n}>{n} 条</option>
              ))}
            </select>
            <button
              onClick={doScreen}
              disabled={busy}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
            >
              {phase === "screening" ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              筛选
            </button>
          </div>

          {/* 快捷预设 */}
          <div className="flex gap-1.5 flex-wrap">
            {["PE < 15 + ROE > 15", "PE < 10 + 股息 > 3%", "高增长 + 低估值", "PB < 1 + 盈利"].map(
              (label, i) => {
                const shortcuts = [
                  "intersect([PE_TTM > 0, PE_TTM < 15, ROETTM > 15])",
                  "intersect([PE_TTM > 0, PE_TTM < 10, DY > 3])",
                  "intersect([PE_TTM > 0, PE_TTM < 20, YOYNI > 30])",
                  "intersect([PB > 0, PB < 1, ROETTM > 5])",
                ];
                return (
                  <button
                    key={i}
                    onClick={() => setExpression(shortcuts[i])}
                    className="px-2 py-1 rounded text-[10px] bg-[#0d1220] border border-[#1a2235] text-slate-500 hover:text-slate-300 hover:border-amber-500/20 transition-colors"
                  >
                    {label}
                  </button>
                );
              },
            )}
          </div>

          {/* 筛选结果 — 模块 5: 代码+名称列表 */}
          {screenResult && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">
                  共 <span className="text-amber-400 font-semibold">{screenResult.count}</span> 只股票
                  {selectedCodes.size > 0 && (
                    <span className="ml-2 text-slate-500">
                      | 已选 {selectedCodes.size} 只
                    </span>
                  )}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={selectAll}
                    className="text-[10px] text-amber-400 hover:text-amber-300 transition-colors"
                  >
                    全选
                  </button>
                  <button
                    onClick={deselectAll}
                    className="text-[10px] text-slate-500 hover:text-slate-400 transition-colors"
                  >
                    清空
                  </button>
                  <button
                    onClick={doReport}
                    disabled={busy}
                    className="flex items-center gap-1 px-3 py-1 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-medium transition-colors disabled:opacity-50"
                  >
                    {phase === "reporting" ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <BarChart3 className="w-3 h-3" />
                    )}
                    回测选中
                  </button>
                </div>
              </div>

              {screenResult.count === 0 ? (
                <div className="text-center py-8 text-slate-500 text-xs">
                  <AlertTriangle className="w-5 h-5 mx-auto mb-2 text-slate-600" />
                  未匹配到股票，请调整筛选条件
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-1.5">
                  {screenResult.candidates.map((c) => {
                    const sel = selectedCodes.has(c.code);
                    return (
                      <button
                        key={c.code}
                        onClick={() => toggleCode(c.code)}
                        className={cn(
                          "flex items-center gap-2 px-2.5 py-2 rounded-lg border text-left transition-all",
                          sel
                            ? "border-emerald-500/40 bg-emerald-500/10"
                            : "border-[#1a2235] bg-[#0d1220] hover:border-amber-500/20",
                        )}
                      >
                        <div
                          className={cn(
                            "w-3.5 h-3.5 rounded border flex-shrink-0 flex items-center justify-center transition-colors",
                            sel
                              ? "bg-emerald-500 border-emerald-500"
                              : "border-[#2a3350]",
                          )}
                        >
                          {sel && <CheckCircle2 className="w-3 h-3 text-white" />}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs text-slate-200 font-mono truncate">{c.code}</div>
                          <div className="text-[10px] text-slate-500 truncate">{c.name}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </Card>

        {/* ── 模块 2: 选股逻辑 AI 分析 ── */}
        {screenResult && screenResult.count > 0 && (
          <Card>
            <CardHeader
              icon={<Lightbulb className="w-4 h-4" />}
              title="选股逻辑分析"
              badge="模块 2"
              action={
                <button
                  onClick={doAnalyze}
                  disabled={busy || !screenResult}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
                >
                  {phase === "analyzing" ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3.5 h-3.5" />
                  )}
                  AI 分析
                </button>
              }
            />

            {analyzeResult ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] font-medium",
                      analyzeResult.llmEnabled
                        ? "bg-cyan-500/20 text-cyan-400"
                        : "bg-slate-500/20 text-slate-400",
                    )}
                  >
                    {analyzeResult.llmEnabled ? `LLM: ${analyzeResult.model}` : "规则兜底"}
                  </span>
                </div>

                {/* 一句话总结 */}
                <div className="p-3 bg-[#0d1220] border border-[#1a2235] rounded-lg text-xs text-slate-300 leading-relaxed">
                  {analyzeResult.summary}
                </div>

                {/* 数据来源 + 分析维度 */}
                <div className="grid grid-cols-2 gap-2">
                  {analyzeResult.dataSources.length > 0 && (
                    <div className="p-2.5 bg-[#0d1220] border border-[#1a2235] rounded-lg">
                      <div className="text-[10px] text-slate-500 mb-1.5">数据来源</div>
                      <div className="flex flex-wrap gap-1">
                        {analyzeResult.dataSources.map((s, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded text-[9px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {analyzeResult.dimensions.length > 0 && (
                    <div className="p-2.5 bg-[#0d1220] border border-[#1a2235] rounded-lg">
                      <div className="text-[10px] text-slate-500 mb-1.5">分析维度</div>
                      <div className="flex flex-wrap gap-1">
                        {analyzeResult.dimensions.map((d, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded text-[9px] bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            {d}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* 推荐理由 */}
                {analyzeResult.reasons.length > 0 && (
                  <div className="p-2.5 bg-[#0d1220] border border-[#1a2235] rounded-lg">
                    <div className="text-[10px] text-slate-500 mb-1.5">推荐理由</div>
                    <ul className="space-y-1">
                      {analyzeResult.reasons.map((r, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-xs text-slate-300">
                          <CheckCircle2 className="w-3 h-3 text-cyan-400 mt-0.5 flex-shrink-0" />
                          {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-xs text-slate-600">
                点击「AI 分析」让 AI 解读当前选股条件背后的投资逻辑
              </div>
            )}
          </Card>
        )}

        {/* ── 模块 3: 回测报告 ── */}
        {reportResult && (
          <Card>
            <CardHeader
              icon={<BarChart3 className="w-4 h-4" />}
              title="回测报告"
              badge="模块 3"
              subtitle={`策略: ${reportResult.strategy} | ${reportResult.startDate} — ${reportResult.endDate}`}
            />

            {/* 聚合 KPI 卡片 */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4">
              <KpiCard
                label="平均总收益"
                value={formatPct(reportResult.aggregate.avgTotalReturn)}
                color={reportResult.aggregate.avgTotalReturn >= 0 ? "text-green-400" : "text-red-400"}
              />
              <KpiCard label="平均夏普" value={reportResult.aggregate.avgSharpe.toFixed(2)} color="text-cyan-400" />
              <KpiCard label="平均回撤" value={formatPct(reportResult.aggregate.avgMaxDrawdown)} color="text-red-400" />
              <KpiCard label="平均胜率" value={reportResult.aggregate.avgWinRate.toFixed(1) + "%"} color="text-amber-400" />
              <KpiCard label="盈利/亏损" value={`${reportResult.aggregate.profitCount}/${reportResult.aggregate.lossCount}`} color="text-slate-300" />
            </div>

            {/* 个股回测表格 */}
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-[#1a2235]">
                    <th className="text-left py-2 pr-4 font-medium">股票</th>
                    <th className="text-right py-2 px-3 font-medium">年化收益</th>
                    <th className="text-right py-2 px-3 font-medium">夏普</th>
                    <th className="text-right py-2 px-3 font-medium">最大回撤</th>
                    <th className="text-right py-2 px-3 font-medium">胜率</th>
                    <th className="text-right py-2 px-3 font-medium">交易次数</th>
                  </tr>
                </thead>
                <tbody>
                  {reportResult.backtests.map((bt) => (
                    <tr key={bt.code} className="border-b border-[#0d1220] hover:bg-[#0d1220]/50">
                      <td className="py-2 pr-4">
                        {bt.error ? (
                          <div className="flex items-center gap-1.5">
                            <XCircle className="w-3 h-3 text-red-400" />
                            <span className="text-slate-400 font-mono">{bt.code}</span>
                            <span className="text-[10px] text-red-400/70">{bt.error}</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5">
                            <a
                              href={`/stock-analysis?code=${bt.code}`}
                              target="_blank"
                              className="group flex items-center gap-1.5 text-slate-200 hover:text-cyan-400 transition-colors"
                            >
                              <span className="font-mono">{bt.code}</span>
                              <span className="text-slate-500 group-hover:text-cyan-400/70">{bt.name}</span>
                              <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 text-cyan-400" />
                            </a>
                          </div>
                        )}
                      </td>
                      {bt.error ? (
                        <td colSpan={5} className="py-2 text-center text-slate-600">—</td>
                      ) : (
                        <>
                          <td className={cn("text-right py-2 px-3 font-mono", bt.annualizedReturn >= 0 ? "text-green-400" : "text-red-400")}>
                            {formatPct(bt.annualizedReturn)}
                          </td>
                          <td className="text-right py-2 px-3 font-mono text-slate-300">{bt.sharpeRatio.toFixed(2)}</td>
                          <td className="text-right py-2 px-3 font-mono text-red-400">{formatPct(bt.maxDrawdown)}</td>
                          <td className="text-right py-2 px-3 font-mono text-slate-300">{bt.winRate.toFixed(1)}%</td>
                          <td className="text-right py-2 px-3 font-mono text-slate-400">{bt.totalTrades}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 净值曲线叠图 — 只展示前5条有效曲线 */}
            {reportResult.backtests.filter((b) => !b.error && b.equityCurve?.length).length > 0 && (
              <EquityCurvesChart
                backtests={reportResult.backtests.filter((b) => !b.error && b.equityCurve?.length).slice(0, 5)}
              />
            )}
          </Card>
        )}

        {/* ── 模块 4: 成败归因 ── */}
        {reportResult?.attribution && (
          <Card>
            <CardHeader
              icon={<Target className="w-4 h-4" />}
              title="成败归因"
              badge="模块 4"
              subtitle={
                reportResult.attribution.llmEnabled
                  ? `AI 模型: ${reportResult.attribution.model}`
                  : "规则兜底"
              }
            />

            <div className="space-y-3">
              {/* 归因总结 — verdict 标签 */}
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "px-2 py-0.5 rounded text-[10px] font-semibold",
                    reportResult.attribution.verdict === "success"
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "bg-red-500/20 text-red-400",
                  )}
                >
                  {reportResult.attribution.verdict === "success" ? "整体成功" : "整体失败"}
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3">
                {/* 归因要点 */}
                <div className={cn(
                  "p-3 rounded-lg border",
                  reportResult.attribution.verdict === "success"
                    ? "bg-emerald-500/5 border-emerald-500/15"
                    : "bg-red-500/5 border-red-500/15",
                )}>
                  <div className="flex items-center gap-1.5 mb-2">
                    {reportResult.attribution.verdict === "success" ? (
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <TrendingDown className="w-3.5 h-3.5 text-red-400" />
                    )}
                    <span className={cn(
                      "text-xs font-semibold",
                      reportResult.attribution.verdict === "success" ? "text-emerald-400" : "text-red-400",
                    )}>
                      {reportResult.attribution.verdict === "success" ? "成功归因" : "失败归因"}
                    </span>
                  </div>
                  <ul className="space-y-1">
                    {reportResult.attribution.points.length > 0 ? (
                      reportResult.attribution.points.map((r, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-xs text-slate-300">
                          {reportResult.attribution.verdict === "success" ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 mt-0.5 flex-shrink-0" />
                          ) : (
                            <AlertTriangle className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
                          )}
                          {r}
                        </li>
                      ))
                    ) : (
                      <li className="text-xs text-slate-500">暂无数据</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* 错误提示 */}
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-2">
            <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <span className="text-xs text-red-300">{error}</span>
          </div>
        )}

        {/* 免责声明 */}
        <p className="text-[10px] text-slate-700 text-center pt-2">
          ⚠️ 以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。投资有风险，决策需谨慎。
        </p>
      </div>
    </div>
  );
}

// ─── 子组件 ─────────────────────────────────────────

function Card({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl p-4">
      {children}
    </div>
  );
}

function CardHeader({
  icon,
  title,
  badge,
  subtitle,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  badge?: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-slate-400">{icon}</span>
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        {badge && (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
            {badge}
          </span>
        )}
        {subtitle && (
          <span className="text-[10px] text-slate-600 truncate ml-2">{subtitle}</span>
        )}
      </div>
      {action}
    </div>
  );
}

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="bg-[#0d1220] border border-[#1a2235] rounded-lg p-2.5 text-center">
      <div className="text-[10px] text-slate-500 mb-1">{label}</div>
      <div className={cn("text-sm font-bold font-mono", color)}>{value}</div>
    </div>
  );
}

function EquityCurvesChart({
  backtests,
}: {
  backtests: { code: string; name: string; equityCurve: { date: string; value: number }[] }[];
}) {
  if (!backtests.length) return null;

  const colors = ["#f59e0b", "#06b6d4", "#10b981", "#8b5cf6", "#f43f5e"];
  const option: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 20, right: 20, bottom: 32, left: 48 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#111827",
      borderColor: "#1e2a3d",
      textStyle: { color: "#e8edf5", fontSize: 11 },
    },
    legend: {
      bottom: 0,
      textStyle: { color: "#5a6a82", fontSize: 10 },
      itemWidth: 10,
      itemHeight: 6,
    },
    xAxis: {
      type: "category",
      data: backtests[0].equityCurve.map((d) => d.date),
      axisLine: { lineStyle: { color: "#1e2a3d" } },
      axisLabel: { color: "#5a6a82", fontSize: 9, interval: Math.max(0, Math.floor(backtests[0].equityCurve.length / 6)) },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#151d2e" } },
      axisLabel: { color: "#5a6a82", fontSize: 10, formatter: (v: number) => (v * 100).toFixed(0) + "%" },
    },
    series: backtests.map((bt, i) => ({
      name: `${bt.code} ${bt.name}`,
      type: "line",
      data: bt.equityCurve.map((d) => d.value),
      showSymbol: false,
      lineStyle: { color: colors[i % colors.length], width: 1.5 },
      emphasis: { focus: "series" },
    })),
  };

  return (
    <div className="mt-4">
      <div className="text-[10px] text-slate-500 mb-2">净值曲线对比（前 5 只）</div>
      <ReactECharts option={option} style={{ height: 240 }} />
    </div>
  );
}
