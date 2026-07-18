"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  LineChart,
  Play,
  Download,
  ListChecks,
  Loader2,
  AlertTriangle,
  Zap,
  Plus,
  Trash2,
  SlidersHorizontal,
} from "lucide-react";
import { cn, formatCurrency, formatPct } from "@/lib/utils";
import {
  fetchPaperBacktestStrategies,
  fetchPaperEventStrategies,
  runPaperBacktest,
  runPaperEventBacktest,
  type PaperBacktestRun,
  type PaperBacktestStrategy,
  type PaperBacktestTrade,
  type PaperEventStrategy,
  type PaperEventRule,
} from "@/lib/api";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { API_BASE } from "@/lib/config";

const STOCK_POOLS = ["沪深300", "中证500", "创业板", "全市场"];

// 事件规则类型中文名
const KIND_LABELS: Record<string, string> = {
  ma_cross: "均线金叉/死叉",
  price_breakout: "价格突破",
  rsi: "RSI 超买超卖",
  drawdown_stop: "回撤止损",
  take_profit: "盈利止盈",
  hold_days: "持仓天数",
};

// 各类型规则的默认参数
function defaultParams(kind: string): Record<string, number> {
  switch (kind) {
    case "ma_cross":
      return { fast: 5, slow: 20 };
    case "price_breakout":
      return { window: 20 };
    case "rsi":
      return { period: 14, threshold: 30 };
    case "drawdown_stop":
    case "take_profit":
      return { pct: 8 };
    case "hold_days":
      return { days: 20 };
    default:
      return {};
  }
}

function kpiColor(v: number, kind: "return" | "plain" = "plain"): string {
  if (kind === "return") return v >= 0 ? "text-emerald-400" : "text-rose-400";
  return "text-slate-100";
}

function Kpi({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={cn("mt-1 text-lg font-semibold tabular-nums", className)}>{value}</div>
    </div>
  );
}

function TradeRow({ t }: { t: PaperBacktestTrade }) {
  const isBuy = t.action === "buy";
  const pnl = t.pnl;
  return (
    <tr className="border-t border-slate-800">
      <td className="px-2 py-1.5 text-slate-300">{t.date}</td>
      <td className="px-2 py-1.5 text-slate-300">{t.code}</td>
      <td className="px-2 py-1.5">
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[10px] font-medium",
            isBuy ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400",
          )}
        >
          {isBuy ? "买入" : "卖出"}
        </span>
      </td>
      <td className="px-2 py-1.5 text-right tabular-nums text-slate-300">
        {t.price.toFixed(2)}
      </td>
      <td className="px-2 py-1.5 text-right tabular-nums text-slate-300">
        {t.shares.toLocaleString()}
      </td>
      <td className="px-2 py-1.5 text-right tabular-nums text-slate-300">
        {t.amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </td>
      <td
        className={cn(
          "px-2 py-1.5 text-right tabular-nums",
          pnl === undefined || pnl === null
            ? "text-slate-500"
            : pnl >= 0
              ? "text-emerald-400"
              : "text-rose-400",
        )}
      >
        {pnl === undefined || pnl === null ? "-" : pnl.toFixed(2)}
      </td>
    </tr>
  );
}

// 单条规则参数编辑器
function RuleParamsEditor({
  rule,
  onChange,
}: {
  rule: PaperEventRule;
  onChange: (params: Record<string, number>) => void;
}) {
  const fields = Object.entries(rule.params);
  return (
    <div className="flex flex-wrap gap-2">
      {fields.map(([k, v]) => (
        <label key={k} className="flex items-center gap-1 text-[11px] text-slate-400">
          {k}
          <input
            type="number"
            className="input input-sm w-16"
            value={v}
            onChange={(e) => onChange({ ...rule.params, [k]: Number(e.target.value) })}
          />
        </label>
      ))}
    </div>
  );
}

export function BacktestPanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [mode, setMode] = useState<"factor" | "event">("factor");

  // —— 因子策略（M8）状态 ——
  const [strategies, setStrategies] = useState<PaperBacktestStrategy[]>([]);
  const [strategy, setStrategy] = useState("均线交叉(MA5/MA20)");
  const [stockPool, setStockPool] = useState("沪深300");
  const [code, setCode] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [initialCapital, setInitialCapital] = useState(1_000_000);

  // —— 事件驱动（M181）状态 ——
  const [eventStrategies, setEventStrategies] = useState<PaperEventStrategy[]>([]);
  const [eventRules, setEventRules] = useState<PaperEventRule[]>([
    { side: "entry", kind: "ma_cross", params: { fast: 5, slow: 20 } },
    { side: "exit", kind: "ma_cross", params: { fast: 5, slow: 20 } },
  ]);
  const [universe, setUniverse] = useState("");
  const [eventCode, setEventCode] = useState("");
  const [stopLoss, setStopLoss] = useState(8);
  const [takeProfit, setTakeProfit] = useState(0);
  const [eventName, setEventName] = useState("事件驱动组合");

  // —— 运行/结果状态 ——
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<PaperBacktestRun | null>(null);
  const [eventRun, setEventRun] = useState<PaperBacktestRun | null>(null);

  // 当前展示结果（按模式切换）
  const activeRun = mode === "event" ? eventRun : run;

  const loadStrategies = useCallback(async () => {
    try {
      const list = await fetchPaperBacktestStrategies();
      setStrategies(list);
      if (list.length && !list.some((s) => s.key === strategy)) {
        setStrategy(list[0].key);
      }
    } catch {
      /* 策略列表失败不阻断主流程 */
    }
  }, [strategy]);

  const loadEventStrategies = useCallback(async () => {
    try {
      const list = await fetchPaperEventStrategies();
      setEventStrategies(list);
    } catch {
      /* 模板失败不阻断主流程 */
    }
  }, []);

  useEffect(() => {
    loadStrategies();
    loadEventStrategies();
  }, [loadStrategies, loadEventStrategies]);

  const handleRun = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      if (mode === "factor") {
        const res = await runPaperBacktest(accountId, {
          strategy,
          stockPool,
          code: code.trim() || null,
          startDate: startDate.trim(),
          endDate: endDate.trim(),
          initialCapital,
        });
        setRun(res);
      } else {
        const codes = universe
          .split(/[\s,，]+/)
          .map((s) => s.trim())
          .filter(Boolean);
        if (!codes.length && !eventCode.trim()) {
          throw new Error("请至少填写一个标的代码（标的宇宙）或单个标的代码");
        }
        if (!eventRules.some((r) => r.side === "entry")) {
          throw new Error("事件驱动策略至少需要一条入场规则");
        }
        const res = await runPaperEventBacktest(accountId, {
          strategyName: eventName.trim() || "事件驱动组合",
          universe: codes,
          code: eventCode.trim() || null,
          startDate: startDate.trim(),
          endDate: endDate.trim(),
          initialCapital,
          rules: eventRules,
          risk: { stopLoss, takeProfit },
        });
        setEventRun(res);
      }
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }, [
    mode,
    accountId,
    strategy,
    stockPool,
    code,
    startDate,
    endDate,
    initialCapital,
    eventName,
    universe,
    eventCode,
    eventRules,
    stopLoss,
    takeProfit,
    onChanged,
  ]);

  const applyTemplate = (key: string) => {
    const tpl = eventStrategies.find((t) => t.key === key);
    if (!tpl) return;
    setEventRules(tpl.rules.map((r) => ({ ...r, params: { ...r.params } })));
    setStopLoss(tpl.risk.stopLoss);
    setTakeProfit(tpl.risk.takeProfit);
  };

  const addRule = () => {
    setEventRules((prev) => [
      ...prev,
      { side: "entry", kind: "ma_cross", params: defaultParams("ma_cross") },
    ]);
  };

  const updateRule = (idx: number, patch: Partial<PaperEventRule>) => {
    setEventRules((prev) =>
      prev.map((r, i) => {
        if (i !== idx) return r;
        if (patch.kind && patch.kind !== r.kind) {
          // 类型变更时重置参数为该类型默认值
          return { ...r, kind: patch.kind, params: defaultParams(patch.kind) };
        }
        return { ...r, ...patch };
      }),
    );
  };

  const removeRule = (idx: number) => {
    setEventRules((prev) => prev.filter((_, i) => i !== idx));
  };

  const dsBadge =
    activeRun?.dataSource === "westock"
      ? "badge-green"
      : activeRun?.dataSource === "mock"
        ? "badge-yellow"
        : "badge-gray";

  return (
    <div className="card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LineChart className="h-4 w-4 text-blue-400" />
          <h2 className="text-sm font-semibold text-slate-200">回测系统 (M8 / M181)</h2>
        </div>
        {/* 模式切换：因子策略 / 事件驱动 */}
        <div className="flex gap-1">
          <button
            onClick={() => setMode("factor")}
            className={cn(
              "px-2.5 py-1 text-[11px] rounded-lg border transition-colors",
              mode === "factor"
                ? "border-blue-500/40 bg-blue-500/10 text-blue-300"
                : "border-slate-700 text-slate-500 hover:text-slate-300",
            )}
          >
            因子/均线策略
          </button>
          <button
            onClick={() => setMode("event")}
            className={cn(
              "px-2.5 py-1 text-[11px] rounded-lg border transition-colors flex items-center gap-1",
              mode === "event"
                ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                : "border-slate-700 text-slate-500 hover:text-slate-300",
            )}
          >
            <Zap className="h-3 w-3" />
            事件驱动
          </button>
        </div>
      </div>

      {/* 配置区 */}
      {mode === "factor" ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-12">
          <div className="md:col-span-4">
            <label className="mb-1 block text-[11px] text-slate-400">策略</label>
            <select
              className="input input-sm w-full"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              {strategies.length === 0 && <option value={strategy}>{strategy}</option>}
              {strategies.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] text-slate-400">股票池</label>
            <select
              className="input input-sm w-full"
              value={stockPool}
              onChange={(e) => setStockPool(e.target.value)}
            >
              {STOCK_POOLS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] text-slate-400">标的代码(可选)</label>
            <input
              className="input input-sm w-full"
              placeholder="如 sh600519"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] text-slate-400">起始日期</label>
            <input
              type="date"
              className="input input-sm w-full"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] text-slate-400">结束日期</label>
            <input
              type="date"
              className="input input-sm w-full"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-[11px] text-slate-400">初始资金(元)</label>
            <input
              type="number"
              step={100000}
              className="input input-sm w-full"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value) || 0)}
            />
          </div>
          <div className="flex items-end md:col-span-2">
            <button
              className="btn-primary btn-sm flex w-full items-center justify-center gap-1.5"
              onClick={handleRun}
              disabled={running}
            >
              {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {running ? "回测中…" : "运行回测"}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {/* 模板 + 名称 */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-12">
            <div className="md:col-span-5">
              <label className="mb-1 block text-[11px] text-slate-400">策略模板（一键预设规则）</label>
              <select
                className="input input-sm w-full"
                defaultValue=""
                onChange={(e) => e.target.value && applyTemplate(e.target.value)}
              >
                <option value="">自定义 / 选择模板…</option>
                {eventStrategies.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-4">
              <label className="mb-1 block text-[11px] text-slate-400">策略名称</label>
              <input
                className="input input-sm w-full"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
              />
            </div>
            <div className="md:col-span-3">
              <label className="mb-1 block text-[11px] text-slate-400">初始资金(元)</label>
              <input
                type="number"
                step={100000}
                className="input input-sm w-full"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value) || 0)}
              />
            </div>
          </div>

          {/* 标的宇宙 + 单标的 + 区间 */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-12">
            <div className="md:col-span-6">
              <label className="mb-1 block text-[11px] text-slate-400">
                标的宇宙（多标的等权，代码空格/逗号分隔）
              </label>
              <textarea
                className="input input-sm w-full h-16 resize-none font-mono"
                placeholder="sh600519 sz000858 sh601318"
                value={universe}
                onChange={(e) => setUniverse(e.target.value)}
              />
            </div>
            <div className="md:col-span-2">
              <label className="mb-1 block text-[11px] text-slate-400">或单标的(可选)</label>
              <input
                className="input input-sm w-full"
                placeholder="sh600519"
                value={eventCode}
                onChange={(e) => setEventCode(e.target.value)}
              />
            </div>
            <div className="md:col-span-2">
              <label className="mb-1 block text-[11px] text-slate-400">起始日期</label>
              <input
                type="date"
                className="input input-sm w-full"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="md:col-span-2">
              <label className="mb-1 block text-[11px] text-slate-400">结束日期</label>
              <input
                type="date"
                className="input input-sm w-full"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* 事件规则构建器 */}
          <div className="rounded-lg border border-slate-700/60 bg-slate-800/30 p-3">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-300">
                <SlidersHorizontal className="h-3.5 w-3.5 text-amber-400" />
                事件规则（入场触发买入 / 出场触发卖出）
              </div>
              <button
                className="btn-secondary btn-xs flex items-center gap-1"
                onClick={addRule}
              >
                <Plus className="h-3 w-3" /> 添加规则
              </button>
            </div>
            <div className="space-y-2">
              {eventRules.map((r, idx) => (
                <div
                  key={idx}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-slate-700/50 bg-slate-800/50 px-2 py-1.5"
                >
                  <select
                    className="input input-xs w-20"
                    value={r.side}
                    onChange={(e) => updateRule(idx, { side: e.target.value as "entry" | "exit" })}
                  >
                    <option value="entry">入场</option>
                    <option value="exit">出场</option>
                  </select>
                  <select
                    className="input input-xs w-32"
                    value={r.kind}
                    onChange={(e) => updateRule(idx, { kind: e.target.value })}
                  >
                    {Object.entries(KIND_LABELS).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <RuleParamsEditor rule={r} onChange={(p) => updateRule(idx, { params: p })} />
                  <button
                    className="ml-auto text-slate-500 hover:text-rose-400"
                    onClick={() => removeRule(idx)}
                    title="删除规则"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* 风控 + 运行 */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-12">
            <div className="md:col-span-3">
              <label className="mb-1 block text-[11px] text-slate-400">止损 %(0=不启用)</label>
              <input
                type="number"
                className="input input-sm w-full"
                value={stopLoss}
                onChange={(e) => setStopLoss(Number(e.target.value) || 0)}
              />
            </div>
            <div className="md:col-span-3">
              <label className="mb-1 block text-[11px] text-slate-400">止盈 %(0=不启用)</label>
              <input
                type="number"
                className="input input-sm w-full"
                value={takeProfit}
                onChange={(e) => setTakeProfit(Number(e.target.value) || 0)}
              />
            </div>
            <div className="flex items-end md:col-span-6">
              <button
                className="btn-primary btn-sm flex w-full items-center justify-center gap-1.5"
                onClick={handleRun}
                disabled={running}
              >
                {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
                {running ? "回测中…" : "运行事件驱动回测"}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          <AlertTriangle className="h-3.5 w-3.5" />
          {error}
        </div>
      )}

      {/* 结果区 */}
      {activeRun && (
        <div className="mt-5">
          <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
            <span>
              标的 <span className="text-slate-300">{activeRun.symbol || "—"}</span>
            </span>
            <span>·</span>
            <span>
              区间 <span className="text-slate-300">{activeRun.startDate || "—"} ~ {activeRun.endDate || "—"}</span>
            </span>
            <span>·</span>
            <span>
              初始资金 <span className="text-slate-300">{formatCurrency(activeRun.initialCapital)}</span>
            </span>
            <span>·</span>
            <span>
              模式 <span className="text-slate-300">{activeRun.mode === "event" ? "事件驱动" : "因子/均线"}</span>
            </span>
            <span>·</span>
            <span>
              运行于 <span className="text-slate-300">{activeRun.createdAt || "—"}</span>
            </span>
            {activeRun.mode === "event" && activeRun.params && (
              <>
                <span>·</span>
                <span>
                  标的数 <span className="text-slate-300">{Array.isArray(activeRun.params.universe) ? activeRun.params.universe.length : "—"}</span>
                </span>
              </>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            <Kpi
              label="总收益率"
              value={formatPct(activeRun.totalReturn)}
              className={kpiColor(activeRun.totalReturn, "return")}
            />
            <Kpi
              label="年化收益"
              value={formatPct(activeRun.annualizedReturn)}
              className={kpiColor(activeRun.annualizedReturn, "return")}
            />
            <Kpi label="夏普比率" value={activeRun.sharpeRatio.toFixed(2)} />
            <Kpi
              label="最大回撤"
              value={formatPct(activeRun.maxDrawdown, false)}
              className="text-rose-400"
            />
            <Kpi label="Calmar" value={activeRun.calmarRatio.toFixed(2)} />
            <Kpi label="胜率" value={formatPct(activeRun.winRate)} />
            <Kpi label="交易次数" value={String(activeRun.totalTrades)} />
          </div>

          <div className="mt-4 rounded-lg border border-slate-700/60 bg-slate-800/40 p-3">
            <div className="mb-2 text-[11px] font-medium text-slate-400">权益曲线</div>
            {activeRun.equityCurve.length > 0 ? (
              <EquityCurveChart data={activeRun.equityCurve} height={320} />
            ) : (
              <div className="py-8 text-center text-xs text-slate-500">本区间无权益曲线数据</div>
            )}
          </div>

          <div className="mt-4">
            <div className="mb-2 flex items-center gap-2 text-[11px] font-medium text-slate-400">
              <ListChecks className="h-3.5 w-3.5" />
              交易明细（{activeRun.trades.length}）
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-700/60">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-800/60 text-slate-400">
                  <tr>
                    <th className="px-2 py-2 font-medium">日期</th>
                    <th className="px-2 py-2 font-medium">代码</th>
                    <th className="px-2 py-2 font-medium">方向</th>
                    <th className="px-2 py-2 text-right font-medium">价格</th>
                    <th className="px-2 py-2 text-right font-medium">股数</th>
                    <th className="px-2 py-2 text-right font-medium">金额</th>
                    <th className="px-2 py-2 text-right font-medium">盈亏</th>
                  </tr>
                </thead>
                <tbody>
                  {activeRun.trades.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-2 py-4 text-center text-slate-500">
                        本区间无完整买卖回合
                      </td>
                    </tr>
                  ) : (
                    activeRun.trades.map((t, i) => <TradeRow key={i} t={t} />)
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 离线报告下载 */}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-slate-500">离线报告：</span>
            <a
              className="btn-secondary btn-xs flex items-center gap-1"
              href={`${API_BASE}/api/paper/backtest/runs/${activeRun.id}/file/index.html`}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-3 w-3" /> HTML 仪表盘
            </a>
            <a
              className="btn-secondary btn-xs flex items-center gap-1"
              href={`${API_BASE}/api/paper/backtest/runs/${activeRun.id}/file/summary.json`}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-3 w-3" /> summary.json
            </a>
            <a
              className="btn-secondary btn-xs flex items-center gap-1"
              href={`${API_BASE}/api/paper/backtest/runs/${activeRun.id}/file/equity.csv`}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-3 w-3" /> equity.csv
            </a>
            <a
              className="btn-secondary btn-xs flex items-center gap-1"
              href={`${API_BASE}/api/paper/backtest/runs/${activeRun.id}/file/trades.csv`}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-3 w-3" /> trades.csv
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
