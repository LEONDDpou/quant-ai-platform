"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  FlaskConical,
  Play,
  Loader2,
  Sparkles,
  Trash2,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  Brain,
  Radar,
  Activity,
} from "lucide-react";
import { cn, formatPct } from "@/lib/utils";
import {
  fetchPaperResearchSessions,
  runPaperResearch,
  backtestPaperResearchIdea,
  deletePaperResearchIdea,
  type PaperResearchSession,
  type PaperStrategyIdea,
  type PaperFactorFinding,
} from "@/lib/api";

// 因子方向 → 颜色
function directionTone(d: string): string {
  if (d === "long") return "text-emerald-400";
  if (d === "short") return "text-rose-400";
  return "text-slate-400";
}
function DirectionIcon({ d }: { d: string }) {
  if (d === "long") return <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />;
  if (d === "short") return <TrendingDown className="w-3.5 h-3.5 text-rose-400" />;
  return <Minus className="w-3.5 h-3.5 text-slate-500" />;
}

// 规则 → 人类可读
function ruleToText(r: { kind: string; params?: Record<string, unknown> }): string {
  const p = r.params || {};
  switch (r.kind) {
    case "ma_cross":
      return `均线交叉(快${p.fast}/慢${p.slow})`;
    case "price_breakout":
      return `价格突破${p.window}日高`;
    case "rsi":
      return `RSI(${p.period}) ${p.direction === "below" ? "跌破" : "升破"}${p.threshold}`;
    case "drawdown_stop":
      return `回撤止损${p.pct}%`;
    case "take_profit":
      return `止盈${p.pct}%`;
    case "hold_days":
      return `持有${p.days}日`;
    default:
      return r.kind;
  }
}

export default function ResearcherAgentPanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [universe, setUniverse] = useState("600519, 300750, 601318, 000858, 600036");
  const [useLlm, setUseLlm] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [sessions, setSessions] = useState<PaperResearchSession[]>([]);
  const [sel, setSel] = useState<PaperResearchSession | null>(null);
  const [btResult, setBtResult] = useState<Record<number, { totalReturn: number; sharpeRatio: number; maxDrawdown: number; winRate: number }>>({});
  const [btId, setBtId] = useState<number | null>(null);
  const [delId, setDelId] = useState<number | null>(null);

  const loadSessions = useCallback(() => {
    fetchPaperResearchSessions(accountId)
      .then((list) => {
        setSessions(list);
        if (list.length > 0) setSel(list[0]);
      })
      .catch(() => {/* 静默：面板初次可能无数据 */});
  }, [accountId]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const runResearch = () => {
    setRunning(true);
    setError("");
    const codes = universe
      .split(/[\s,，]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    runPaperResearch({ accountId, universe: codes, useLlm, maxIdeas: 3 })
      .then((res) => {
        setSessions((prev) => [res.session, ...prev]);
        setSel(res.session);
        onChanged?.();
      })
      .catch((e) => setError(e instanceof Error ? e.message : "研究失败"))
      .finally(() => setRunning(false));
  };

  const onBacktest = (idea: PaperStrategyIdea) => {
    setBtId(idea.id);
    backtestPaperResearchIdea(idea.id, accountId)
      .then((r) => {
        setBtResult((prev) => ({
          ...prev,
          [idea.id]: {
            totalReturn: r.totalReturn,
            sharpeRatio: r.sharpeRatio,
            maxDrawdown: r.maxDrawdown,
            winRate: r.winRate,
          },
        }));
        // 刷新会话，反映 backtested 标记
        loadSessions();
      })
      .catch((e) => setError(e instanceof Error ? e.message : "回测失败"))
      .finally(() => setBtId(null));
  };

  const onDelete = (idea: PaperStrategyIdea) => {
    setDelId(idea.id);
    deletePaperResearchIdea(idea.id)
      .then(() => {
        setSel((s) => (s ? { ...s, ideas: s.ideas.filter((x) => x.id !== idea.id) } : s));
        loadSessions();
        onChanged?.();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "删除失败"))
      .finally(() => setDelId(null));
  };

  return (
    <div className="card p-5 space-y-5">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              研究员 Agent
              <span className="text-[10px] font-normal text-slate-500">自动挖掘因子 · 生成策略</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              因子挖掘（规则确定性 / 大模型双轨）→ 事件驱动策略想法 → 一键回测（M181）
            </p>
          </div>
        </div>
        <span className="text-[10px] text-slate-600 flex items-center gap-1">
          <Activity className="w-3 h-3 text-emerald-400" /> 后台每小时自动研究
        </span>
      </div>

      {/* 运行区 */}
      <div className="card bg-[#0b0f19] p-4 space-y-3">
        <div>
          <label className="text-xs text-slate-400 mb-1.5 block">研究标的宇宙（逗号分隔代码）</label>
          <textarea
            value={universe}
            onChange={(e) => setUniverse(e.target.value)}
            rows={2}
            className="w-full bg-[#0e1422] border border-[#1e2a3d] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500/50"
            placeholder="600519, 300750, ..."
          />
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={useLlm}
              onChange={(e) => setUseLlm(e.target.checked)}
              className="accent-violet-500"
            />
            启用大模型生成（需配置 LLM_API_KEY，否则回退规则）
          </label>
          <button onClick={runResearch} disabled={running} className="btn-primary flex items-center gap-1.5 ml-auto">
            {running ? <><Loader2 className="w-4 h-4 animate-spin" />研究中…</> : <><Play className="w-4 h-4" />运行研究</>}
          </button>
        </div>
      </div>

      {error && <div className="text-rose-400 text-sm">{error}</div>}

      {/* 会话选择 */}
      {sessions.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-500">历史会话：</span>
          {sessions.slice(0, 8).map((s) => (
            <button
              key={s.id}
              onClick={() => setSel(s)}
              className={cn(
                "px-2.5 py-1 text-[11px] rounded border transition-colors",
                sel?.id === s.id
                  ? "border-violet-500/50 bg-violet-500/10 text-violet-200"
                  : "border-[#1e2a3d] text-slate-500 hover:text-slate-300",
              )}
            >
              #{s.id} · {s.mode === "llm" ? "LLM" : "规则"}
            </button>
          ))}
          <button onClick={loadSessions} className="btn-ghost text-[11px] flex items-center gap-1">
            <RefreshCw className="w-3 h-3" />刷新
          </button>
        </div>
      )}

      {sel && (
        <div className="space-y-4">
          {/* 会话摘要 */}
          <div className="text-xs text-slate-400 bg-[#0b0f19] border border-[#1e2a3d] rounded-lg px-3 py-2">
            <span className="text-slate-500">会话 #{sel.id}</span> · {sel.summary || "（无摘要）"}
          </div>

          {/* 因子结论 */}
          <div>
            <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-1.5">
              <Radar className="w-4 h-4 text-violet-400" /> 挖掘因子（{sel.factors.length}）
            </h3>
            {sel.factors.length === 0 ? (
              <div className="text-xs text-slate-600">本次未挖掘到有效因子（可能行情不足）。</div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {sel.factors.map((f: PaperFactorFinding) => (
                  <div key={f.id} className="card p-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-slate-200">{f.name}</span>
                      <DirectionIcon d={f.direction} />
                    </div>
                    <div className="text-[10px] text-slate-600 mb-1.5">{f.description}</div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className={cn("h-full rounded-full", f.direction === "short" ? "bg-rose-500/70" : f.direction === "long" ? "bg-emerald-500/70" : "bg-slate-500/70")}
                          style={{ width: `${Math.max(2, Math.min(100, f.score))}%` }}
                        />
                      </div>
                      <span className={cn("text-xs font-mono", directionTone(f.direction))}>{f.score.toFixed(0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 策略想法 */}
          <div>
            <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-1.5">
              <Brain className="w-4 h-4 text-violet-400" /> 策略想法（{sel.ideas.length}）
            </h3>
            {sel.ideas.length === 0 ? (
              <div className="text-xs text-slate-600">本次未生成策略想法。</div>
            ) : (
              <div className="space-y-3">
                {sel.ideas.map((idea) => (
                  <div key={idea.id} className="card p-4 border border-[#1e2a3d]">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-slate-100">{idea.name}</span>
                          {idea.backtested && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
                              已回测 #{idea.backtestRunId}
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5">{idea.description}</div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => onBacktest(idea)}
                          disabled={btId === idea.id}
                          className="btn-primary text-[11px] flex items-center gap-1"
                        >
                          {btId === idea.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                          回测
                        </button>
                        <button
                          onClick={() => onDelete(idea)}
                          disabled={delId === idea.id}
                          className="btn-ghost text-[11px] p-1.5"
                          title="删除"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                        </button>
                      </div>
                    </div>

                    {/* 规则预览 */}
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      <span className="text-[10px] text-slate-600">入场：</span>
                      {idea.entryRules.map((r, i) => (
                        <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 font-mono">
                          {ruleToText(r)}
                        </span>
                      ))}
                      <span className="text-[10px] text-slate-600 ml-2">出场：</span>
                      {idea.exitRules.map((r, i) => (
                        <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-300 font-mono">
                          {ruleToText(r)}
                        </span>
                      ))}
                      <span className="text-[10px] text-slate-600 ml-2">
                        风控：止损{idea.risk.stopLoss ?? "-"}% / 止盈{idea.risk.takeProfit ?? "-"}%
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500 mt-2">{idea.logic}</div>

                    {/* 回测结果 */}
                    {btResult[idea.id] && (
                      <div className="grid grid-cols-4 gap-2 mt-3">
                        <Kpi label="累计收益" value={formatPct(btResult[idea.id].totalReturn)} tone={btResult[idea.id].totalReturn >= 0 ? "pos" : "neg"} />
                        <Kpi label="夏普" value={btResult[idea.id].sharpeRatio.toFixed(2)} tone={btResult[idea.id].sharpeRatio >= 0 ? "pos" : "neg"} />
                        <Kpi label="最大回撤" value={formatPct(btResult[idea.id].maxDrawdown)} tone="neg" />
                        <Kpi label="胜率" value={`${btResult[idea.id].winRate.toFixed(0)}%`} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {!sel && !running && (
        <div className="text-center text-slate-600 text-sm py-8">
          尚未运行研究。填写标的宇宙后点击「运行研究」，研究员 Agent 将自动挖掘因子并生成可回测策略。
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="bg-[#0b0f19] border border-[#1e2a3d] rounded-lg px-2 py-1.5">
      <div className="text-[10px] text-slate-500 mb-0.5">{label}</div>
      <div className={cn("font-mono text-sm font-semibold", tone === "pos" ? "text-emerald-400" : tone === "neg" ? "text-rose-400" : "text-slate-200")}>{value}</div>
    </div>
  );
}
