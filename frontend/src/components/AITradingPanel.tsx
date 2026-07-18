"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Bot,
  Play,
  Settings2,
  Signal,
  ListChecks,
  ScrollText,
  RefreshCw,
  Plus,
  Trash2,
  Save,
} from "lucide-react";
import { cn, formatCurrency, formatPct, getColorClass } from "@/lib/utils";
import {
  fetchPaperStrategies,
  createPaperStrategy,
  togglePaperStrategy,
  runPaperAutoTrade,
  fetchPaperSignals,
  fetchPaperAILogs,
  fetchPaperAutoStatus,
  fetchPaperPositions,
  setPaperHoldingSLTP,
  type PaperStrategyConfig,
  type PaperSignal,
  type PaperAILog,
  type PaperAutoStatus,
  type PaperPosition,
} from "@/lib/api";

type TabKey = "strategy" | "signals" | "holdings" | "logs";

const DEFAULT_UNIVERSE = ["600519", "300750", "601318", "000858", "600036", "002594"];

function fmt(n: number | undefined | null): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "-";
  return formatCurrency(n);
}

export function AITradingPanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [tab, setTab] = useState<TabKey>("strategy");
  const [strategies, setStrategies] = useState<PaperStrategyConfig[]>([]);
  const [signals, setSignals] = useState<PaperSignal[]>([]);
  const [logs, setLogs] = useState<PaperAILog[]>([]);
  const [status, setStatus] = useState<PaperAutoStatus | null>(null);
  const [holdings, setHoldings] = useState<PaperPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 创建策略表单
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("AI 双均线+RSI 策略");
  const [universeText, setUniverseText] = useState(DEFAULT_UNIVERSE.join(", "));
  const [maxPositions, setMaxPositions] = useState(5);
  const [perTradePct, setPerTradePct] = useState(0.15);
  const [stopLossPct, setStopLossPct] = useState(0.08);
  const [takeProfitPct, setTakeProfitPct] = useState(0.2);

  const refresh = useCallback(async () => {
    if (accountId == null) return;
    setLoading(true);
    setError(null);
    try {
      const [s, sig, lg, st, pos] = await Promise.all([
        fetchPaperStrategies(accountId),
        fetchPaperSignals(accountId, 30),
        fetchPaperAILogs(accountId, 30),
        fetchPaperAutoStatus(accountId),
        fetchPaperPositions(accountId),
      ]);
      setStrategies(s);
      setSignals(sig);
      setLogs(lg);
      setStatus(st);
      setHoldings(pos.filter((p) => p.shares > 0));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    if (accountId != null) refresh();
  }, [accountId, refresh]);

  const handleRun = async () => {
    if (accountId == null) return;
    setRunning(true);
    setError(null);
    try {
      await runPaperAutoTrade(accountId);
      await refresh();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const handleToggle = async (s: PaperStrategyConfig) => {
    if (accountId == null) return;
    try {
      await togglePaperStrategy(accountId, s.id, !s.enabled);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleCreate = async () => {
    if (accountId == null) return;
    const universe = universeText
      .split(/[,\s]+/)
      .map((x) => x.trim())
      .filter(Boolean);
    try {
      await createPaperStrategy(accountId, {
        name: name.trim() || "AI 策略",
        enabled: true,
        params: {
          universe,
          maxPositions,
          perTradePct,
          stopLossPct,
          takeProfitPct,
        },
      });
      setCreating(false);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "strategy", label: "策略", icon: <Settings2 className="w-3.5 h-3.5" />, count: strategies.length },
    { key: "signals", label: "信号", icon: <Signal className="w-3.5 h-3.5" />, count: signals.length },
    { key: "holdings", label: "持仓止损/止盈", icon: <ListChecks className="w-3.5 h-3.5" />, count: holdings.length },
    { key: "logs", label: "AI 日志", icon: <ScrollText className="w-3.5 h-3.5" />, count: logs.length },
  ];

  if (accountId == null) {
    return (
      <div className="card p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-cyan-400" />
          <h3 className="section-title">AI 自动交易 (M7)</h3>
        </div>
        <div className="text-xs text-slate-600">请先选择一个模拟账户。</div>
      </div>
    );
  }

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Bot className="w-4 h-4 text-cyan-400" />
        <h3 className="section-title">AI 自动交易 (M7)</h3>
        {status && (
          <span
            className={cn(
              "badge",
              status.enabledStrategies > 0 ? "badge-green" : "badge-gray",
            )}
          >
            {status.enabledStrategies > 0 ? `${status.enabledStrategies} 个策略运行中` : "未启用策略"}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            className="btn btn-xs btn-primary flex items-center gap-1"
            onClick={handleRun}
            disabled={running || loading}
          >
            <Play className="w-3 h-3" />
            {running ? "运行中…" : "运行一轮"}
          </button>
          <button
            className="btn btn-xs btn-ghost flex items-center gap-1"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
            刷新
          </button>
        </div>
      </div>

      {status && status.lastRunAt && (
        <div className="text-[11px] text-slate-500">
          最近运行：{status.lastRunAt}
          {status.dataSource && ` · 数据源 ${status.dataSource}`}
          {Object.keys(status.lastRunSummary).length > 0 &&
            ` · 信号 ${status.lastRunSummary.signals ?? 0} / 买入 ${status.lastRunSummary.buys ?? 0} / 卖出 ${status.lastRunSummary.sells ?? 0} / 触发 ${status.lastRunSummary.stopTriggers ?? 0}`}
        </div>
      )}

      {error && (
        <div className="text-[11px] text-red-400 bg-red-500/10 border border-red-500/30 rounded px-2 py-1">
          {error}
        </div>
      )}

      {/* Tab 切换 */}
      <div className="flex items-center gap-1 border-b border-slate-800">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={cn(
              "px-3 py-1.5 text-xs flex items-center gap-1 border-b-2 -mb-px transition-colors",
              tab === t.key
                ? "border-cyan-400 text-cyan-300"
                : "border-transparent text-slate-500 hover:text-slate-300",
            )}
            onClick={() => setTab(t.key)}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && (
              <span className="text-[10px] text-slate-600">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {tab === "strategy" && (
        <StrategyTab
          strategies={strategies}
          creating={creating}
          setCreating={setCreating}
          name={name}
          setName={setName}
          universeText={universeText}
          setUniverseText={setUniverseText}
          maxPositions={maxPositions}
          setMaxPositions={setMaxPositions}
          perTradePct={perTradePct}
          setPerTradePct={setPerTradePct}
          stopLossPct={stopLossPct}
          setStopLossPct={setStopLossPct}
          takeProfitPct={takeProfitPct}
          setTakeProfitPct={setTakeProfitPct}
          onToggle={handleToggle}
          onCreate={handleCreate}
        />
      )}

      {tab === "signals" && <SignalsTab signals={signals} />}

      {tab === "holdings" && (
        <HoldingsTab
          holdings={holdings}
          onSave={async (code, sl, tp) => {
            await setPaperHoldingSLTP(accountId, code, sl, tp);
            await refresh();
            onChanged?.();
          }}
        />
      )}

      {tab === "logs" && <LogsTab logs={logs} />}
    </div>
  );
}

// ============================================================
// 策略子面板
// ============================================================
function StrategyTab({
  strategies,
  creating,
  setCreating,
  name,
  setName,
  universeText,
  setUniverseText,
  maxPositions,
  setMaxPositions,
  perTradePct,
  setPerTradePct,
  stopLossPct,
  setStopLossPct,
  takeProfitPct,
  setTakeProfitPct,
  onToggle,
  onCreate,
}: {
  strategies: PaperStrategyConfig[];
  creating: boolean;
  setCreating: (v: boolean) => void;
  name: string;
  setName: (v: string) => void;
  universeText: string;
  setUniverseText: (v: string) => void;
  maxPositions: number;
  setMaxPositions: (v: number) => void;
  perTradePct: number;
  setPerTradePct: (v: number) => void;
  stopLossPct: number;
  setStopLossPct: (v: number) => void;
  takeProfitPct: number;
  setTakeProfitPct: (v: number) => void;
  onToggle: (s: PaperStrategyConfig) => void;
  onCreate: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      {strategies.length === 0 && !creating && (
        <div className="text-xs text-slate-600">尚无策略，点击下方「新建策略」开始。</div>
      )}

      {strategies.map((s) => (
        <div key={s.id} className="rounded border border-slate-800 p-2.5 flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <button
              className={cn(
                "w-9 h-5 rounded-full transition-colors relative",
                s.enabled ? "bg-cyan-500/80" : "bg-slate-700",
              )}
              onClick={() => onToggle(s)}
              title={s.enabled ? "点击停用" : "点击启用"}
            >
              <span
                className={cn(
                  "absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all",
                  s.enabled ? "left-4" : "left-0.5",
                )}
              />
            </button>
            <span className="text-sm text-slate-200 font-medium">{s.name}</span>
            <span className={cn("badge", s.enabled ? "badge-green" : "badge-gray")}>
              {s.enabled ? "启用" : "停用"}
            </span>
          </div>
          <div className="text-[11px] text-slate-500 flex flex-wrap gap-x-3 gap-y-0.5">
            <span>监控 {Array.isArray(s.params.universe) ? (s.params.universe as string[]).length : 0} 只</span>
            <span>最大持仓 {String(s.params.maxPositions ?? "-")}</span>
            <span>单笔 {(Number(s.params.perTradePct ?? 0) * 100).toFixed(0)}%</span>
            <span>止损 {(Number(s.params.stopLossPct ?? 0) * 100).toFixed(0)}%</span>
            <span>止盈 {(Number(s.params.takeProfitPct ?? 0) * 100).toFixed(0)}%</span>
          </div>
        </div>
      ))}

      {creating && (
        <div className="rounded border border-cyan-500/30 bg-cyan-500/5 p-3 flex flex-col gap-2">
          <div className="text-xs text-cyan-300 font-medium">新建 AI 策略</div>
          <label className="text-[11px] text-slate-400">
            策略名称
            <input
              className="input input-sm mt-1 w-full"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="text-[11px] text-slate-400">
            监控标的（逗号分隔，留空用默认池）
            <input
              className="input input-sm mt-1 w-full"
              value={universeText}
              onChange={(e) => setUniverseText(e.target.value)}
            />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <NumberField label="最大持仓数" value={maxPositions} onChange={setMaxPositions} />
            <NumberField
              label="单笔占比(%)"
              value={Math.round(perTradePct * 100)}
              onChange={(v) => setPerTradePct(v / 100)}
            />
            <NumberField
              label="止损(%)"
              value={Math.round(stopLossPct * 100)}
              onChange={(v) => setStopLossPct(v / 100)}
            />
            <NumberField
              label="止盈(%)"
              value={Math.round(takeProfitPct * 100)}
              onChange={(v) => setTakeProfitPct(v / 100)}
            />
          </div>
          <div className="flex items-center gap-2 justify-end">
            <button className="btn btn-xs btn-ghost" onClick={() => setCreating(false)}>
              取消
            </button>
            <button className="btn btn-xs btn-primary flex items-center gap-1" onClick={onCreate}>
              <Plus className="w-3 h-3" /> 创建并启用
            </button>
          </div>
        </div>
      )}

      {!creating && (
        <button
          className="btn btn-xs btn-ghost flex items-center gap-1 self-start"
          onClick={() => setCreating(true)}
        >
          <Plus className="w-3 h-3" /> 新建策略
        </button>
      )}
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="text-[11px] text-slate-400">
      {label}
      <input
        type="number"
        className="input input-sm mt-1 w-full"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

// ============================================================
// 信号子面板
// ============================================================
function SignalsTab({ signals }: { signals: PaperSignal[] }) {
  if (signals.length === 0)
    return <div className="text-xs text-slate-600">暂无信号，运行策略后生成。</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-1 px-1">标的</th>
            <th className="text-left py-1 px-1">信号</th>
            <th className="text-right py-1 px-1">强度</th>
            <th className="text-left py-1 px-1">理由</th>
            <th className="text-right py-1 px-1">时间</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s) => (
            <tr key={s.id} className="border-b border-slate-800/50">
              <td className="py-1 px-1 text-slate-200">
                {s.name} <span className="text-slate-500">{s.code}</span>
              </td>
              <td className="py-1 px-1">
                <span
                  className={cn(
                    "badge",
                    s.signalType === "buy"
                      ? "badge-green"
                      : s.signalType === "sell"
                        ? "badge-red"
                        : "badge-gray",
                  )}
                >
                  {s.signalType === "buy" ? "买入" : s.signalType === "sell" ? "卖出" : "持有"}
                </span>
              </td>
              <td className="py-1 px-1 text-right text-slate-300">{s.strength.toFixed(0)}</td>
              <td className="py-1 px-1 text-slate-400 max-w-[280px] truncate" title={s.reason}>
                {s.reason}
              </td>
              <td className="py-1 px-1 text-right text-slate-500">
                {s.createdAt?.slice(5, 16)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================
// 持仓止损/止盈子面板
// ============================================================
function HoldingsTab({
  holdings,
  onSave,
}: {
  holdings: PaperPosition[];
  onSave: (code: string, sl: number, tp: number) => Promise<void>;
}) {
  const [drafts, setDrafts] = useState<Record<string, { sl: string; tp: string }>>({});
  const [busy, setBusy] = useState<string | null>(null);

  if (holdings.length === 0)
    return <div className="text-xs text-slate-600">当前无持仓，AI 买入后会自动回写止损/止盈。</div>;

  const getDraft = (p: PaperPosition) => {
    const d = drafts[p.code];
    if (d) return d;
    return { sl: String(p.stopLossPrice ?? ""), tp: String(p.takeProfitPrice ?? "") };
  };

  const save = async (p: PaperPosition) => {
    const d = getDraft(p);
    const sl = parseFloat(d.sl);
    const tp = parseFloat(d.tp);
    if (Number.isNaN(sl) || Number.isNaN(tp)) return;
    setBusy(p.code);
    try {
      await onSave(p.code, sl, tp);
      setDrafts((prev) => {
        const n = { ...prev };
        delete n[p.code];
        return n;
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-1 px-1">标的</th>
            <th className="text-right py-1 px-1">成本</th>
            <th className="text-right py-1 px-1">现价</th>
            <th className="text-right py-1 px-1">止损价</th>
            <th className="text-right py-1 px-1">止盈价</th>
            <th className="text-right py-1 px-1">操作</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((p) => {
            const d = getDraft(p);
            return (
              <tr key={p.code} className="border-b border-slate-800/50">
                <td className="py-1 px-1 text-slate-200">
                  {p.name} <span className="text-slate-500">{p.code}</span>
                </td>
                <td className="py-1 px-1 text-right text-slate-300">{fmt(p.costPrice)}</td>
                <td className={cn("py-1 px-1 text-right", getColorClass(p.pnlPct))}>
                  {fmt(p.currentPrice)}
                </td>
                <td className="py-1 px-1 text-right">
                  <input
                    className="input input-xs w-20 text-right"
                    value={d.sl}
                    onChange={(e) =>
                      setDrafts((prev) => ({ ...prev, [p.code]: { ...d, sl: e.target.value } }))
                    }
                  />
                </td>
                <td className="py-1 px-1 text-right">
                  <input
                    className="input input-xs w-20 text-right"
                    value={d.tp}
                    onChange={(e) =>
                      setDrafts((prev) => ({ ...prev, [p.code]: { ...d, tp: e.target.value } }))
                    }
                  />
                </td>
                <td className="py-1 px-1 text-right">
                  <button
                    className="btn btn-xs btn-primary flex items-center gap-1"
                    disabled={busy === p.code}
                    onClick={() => save(p)}
                  >
                    <Save className="w-3 h-3" /> 保存
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================
// 日志子面板
// ============================================================
function LogsTab({ logs }: { logs: PaperAILog[] }) {
  if (logs.length === 0)
    return <div className="text-xs text-slate-600">暂无 AI 日志。</div>;
  return (
    <div className="flex flex-col gap-1.5 max-h-80 overflow-y-auto">
      {logs.map((l) => (
        <div key={l.id} className="rounded border border-slate-800 p-2 text-[11px]">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "badge",
                l.level === "error"
                  ? "badge-red"
                  : l.level === "warn"
                    ? "badge-yellow"
                    : "badge-gray",
              )}
            >
              {l.level}
            </span>
            <span className="text-slate-500">{l.createdAt?.slice(5, 16)}</span>
          </div>
          <div className="text-slate-300 mt-1 leading-relaxed">{l.message}</div>
        </div>
      ))}
    </div>
  );
}
