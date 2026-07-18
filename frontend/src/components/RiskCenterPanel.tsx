"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ShieldAlert,
  SlidersHorizontal,
  ScanLine,
  AlertTriangle,
  Plus,
  Trash2,
  Check,
  CheckCheck,
  RefreshCw,
  ListChecks,
  FileText,
  Radio,
} from "lucide-react";
import { cn, formatCurrency, formatPct, getColorClass } from "@/lib/utils";
import {
  fetchPaperRiskConfig,
  updatePaperRiskConfig,
  fetchPaperRiskMetrics,
  fetchPaperRiskEvents,
  scanPaperRisk,
  fetchPaperRiskRules,
  createPaperRiskRule,
  updatePaperRiskRule,
  deletePaperRiskRule,
  ackPaperRiskEvent,
  ackAllPaperRiskEvents,
  fetchPaperRiskReport,
  type PaperRiskConfig,
  type PaperRiskMetrics,
  type PaperRiskEvent,
  type PaperRiskRule,
  type PaperRiskReport,
  type PaperRiskRuleType,
} from "@/lib/api";

// 规则类型中文标签
const RULE_TYPE_LABEL: Record<PaperRiskRuleType, string> = {
  SECTOR_CONCENTRATION: "行业集中度",
  MAX_DRAWDOWN: "最大回撤",
  LEVERAGE: "杠杆(仓位)上限",
  BLACKLIST: "黑名单标的",
  OVERNIGHT_LIMIT: "隔夜持仓占比",
  CUSTOM: "自定义",
};

const SEVERITY_LABEL: Record<string, string> = {
  warn: "提示",
  high: "重要",
  critical: "严重",
};

// ============================================================
// 通用小组件
// ============================================================
function RiskBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    ok: "badge badge-green",
    warn: "badge badge-yellow",
    breach: "badge badge-red",
  };
  const label: Record<string, string> = { ok: "正常", warn: "预警", breach: "突破" };
  return <span className={map[status] || "badge badge-gray"}>{label[status] || status}</span>;
}

function RiskBar({
  label,
  ratio,
  limit,
  warnAt = 0.8,
}: {
  label: string;
  ratio: number;
  limit: number;
  warnAt?: number;
}) {
  const pct = limit > 0 ? Math.min(100, (ratio / limit) * 100) : 0;
  const cls = pct >= 100 ? "bg-red-500" : pct >= warnAt * 100 ? "bg-yellow-500" : "bg-cyan-500";
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-[11px]">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-slate-200">
          {(ratio * 100).toFixed(1)}% / {(limit * 100).toFixed(0)}%
        </span>
      </div>
      <div className="h-1.5 rounded bg-slate-700/60 overflow-hidden">
        <div className={cn("h-full", cls)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ============================================================
// 智能风控中心主面板
// ============================================================
export function RiskCenterPanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [config, setConfig] = useState<PaperRiskConfig | null>(null);
  const [metrics, setMetrics] = useState<PaperRiskMetrics | null>(null);
  const [events, setEvents] = useState<PaperRiskEvent[]>([]);
  const [rules, setRules] = useState<PaperRiskRule[]>([]);
  const [report, setReport] = useState<PaperRiskReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [monitorOn, setMonitorOn] = useState(true); // 后端默认开启自动监控循环
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // 规则编辑抽屉
  const [editing, setEditing] = useState<PaperRiskRule | null>(null);
  const [showRuleForm, setShowRuleForm] = useState(false);

  const flash = (ok: boolean, text: string) => {
    setMsg({ ok, text });
    setTimeout(() => setMsg(null), 2500);
  };

  // —— 一次性加载全部数据 ——
  const reload = useCallback(async () => {
    if (accountId === null) return;
    setLoading(true);
    try {
      const [cfg, m, ev, rl, rp] = await Promise.all([
        fetchPaperRiskConfig(accountId),
        fetchPaperRiskMetrics(accountId),
        fetchPaperRiskEvents(accountId, 50),
        fetchPaperRiskRules(accountId),
        fetchPaperRiskReport(accountId),
      ]);
      setConfig(cfg);
      setMetrics(m);
      setEvents(ev);
      setRules(rl);
      setReport(rp);
    } catch (e: any) {
      flash(false, "加载风控数据失败：" + (e?.message ?? "未知错误"));
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    reload();
  }, [reload]);

  // —— 保存风控阈值 ——
  const handleSaveConfig = async (patch: Partial<PaperRiskConfig>) => {
    if (accountId === null) return;
    try {
      const saved = await updatePaperRiskConfig(accountId, patch);
      setConfig(saved);
      await reload();
      flash(true, "风控参数已保存");
    } catch (e: any) {
      flash(false, "保存失败：" + (e?.message ?? "未知错误"));
    }
  };

  // —— 手动扫描 ——
  const handleScan = async () => {
    if (accountId === null) return;
    try {
      const r = await scanPaperRisk(accountId);
      await reload();
      flash(true, r.recorded > 0 ? `扫描完成，新增 ${r.recorded} 条风险事件` : "扫描完成，无新增突破");
    } catch (e: any) {
      flash(false, "扫描失败：" + (e?.message ?? "未知错误"));
    }
  };

  // —— 事件已读 ——
  const handleAck = async (eventId: number) => {
    if (accountId === null) return;
    try {
      await ackPaperRiskEvent(accountId, eventId);
      setEvents((prev) => prev.map((e) => (e.id === eventId ? { ...e, acked: true } : e)));
      await reload();
    } catch (e: any) {
      flash(false, "已读失败：" + (e?.message ?? "未知错误"));
    }
  };
  const handleAckAll = async () => {
    if (accountId === null) return;
    try {
      const r = await ackAllPaperRiskEvents(accountId);
      await reload();
      flash(true, `已处理 ${r.acked} 条风险事件`);
    } catch (e: any) {
      flash(false, "批量已读失败：" + (e?.message ?? "未知错误"));
    }
  };

  // —— 规则 CRUD ——
  const handleCreateRule = async (body: Parameters<typeof createPaperRiskRule>[1]) => {
    if (accountId === null) return;
    try {
      await createPaperRiskRule(accountId, body);
      setShowRuleForm(false);
      setEditing(null);
      await reload();
      flash(true, "规则已创建");
    } catch (e: any) {
      flash(false, "创建规则失败：" + (e?.message ?? "未知错误"));
    }
  };
  const handleUpdateRule = async (ruleId: number, body: Parameters<typeof updatePaperRiskRule>[2]) => {
    if (accountId === null) return;
    try {
      await updatePaperRiskRule(accountId, ruleId, body);
      setShowRuleForm(false);
      setEditing(null);
      await reload();
      flash(true, "规则已更新");
    } catch (e: any) {
      flash(false, "更新规则失败：" + (e?.message ?? "未知错误"));
    }
  };
  const handleDeleteRule = async (ruleId: number) => {
    if (accountId === null) return;
    try {
      await deletePaperRiskRule(accountId, ruleId);
      await reload();
      flash(true, "规则已删除");
    } catch (e: any) {
      flash(false, "删除规则失败：" + (e?.message ?? "未知错误"));
    }
  };
  const toggleRule = async (r: PaperRiskRule) => {
    if (accountId === null) return;
    try {
      await updatePaperRiskRule(accountId, r.id, {
        name: r.name,
        ruleType: r.ruleType,
        threshold: r.threshold,
        scope: r.scope,
        enabled: !r.enabled,
        severity: r.severity,
        detail: r.detail,
      });
      await reload();
    } catch (e: any) {
      flash(false, "切换失败：" + (e?.message ?? "未知错误"));
    }
  };

  if (accountId === null) {
    return (
      <div className="card p-8 flex items-center justify-center text-slate-600 text-sm">
        请先在左侧选择模拟账户，进入「智能风控中心」
      </div>
    );
  }

  return (
    <div className="card p-4 flex flex-col gap-4">
      {/* 头部 */}
      <div className="flex items-center gap-2 flex-wrap">
        <ShieldAlert className="w-4 h-4 text-orange-400" />
        <h3 className="section-title">智能风控中心</h3>
        {metrics && (
          <span className="ml-1">
            <RiskBadge status={metrics.overallStatus} />
          </span>
        )}
        <span
          className={cn(
            "badge ml-1 flex items-center gap-1",
            monitorOn ? "badge-live" : "badge-gray",
          )}
          title="后端每 60s 自动扫描全账户风险与自定义规则"
        >
          <Radio className="w-3 h-3" /> {monitorOn ? "自动监控中" : "未连接"}
        </span>
        <button
          onClick={handleScan}
          className="badge badge-gray flex items-center gap-1 hover:bg-slate-700 ml-auto"
          title="手动触发一次风险扫描"
        >
          <ScanLine className="w-3 h-3" /> 扫描
        </button>
        <button
          onClick={() => reload()}
          className="badge badge-cyan flex items-center gap-1 hover:opacity-80"
        >
          <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} /> 刷新
        </button>
      </div>

      {msg && (
        <div className={cn("text-[11px]", msg.ok ? "text-emerald-400" : "text-red-400")}>{msg.text}</div>
      )}

      {/* 1) 实时指标 */}
      {metrics && (
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded bg-slate-800/50 p-2">
              <div className="text-[10px] text-slate-500">今日盈亏</div>
              <div className={cn("font-mono text-sm", metrics.todayPnl >= 0 ? "text-emerald-400" : "text-red-400")}>
                {formatCurrency(metrics.todayPnl)}
              </div>
            </div>
            <div className="rounded bg-slate-800/50 p-2">
              <div className="text-[10px] text-slate-500">今日亏损 / 上限</div>
              <div className={cn("font-mono text-sm", metrics.dailyLossRatio >= 1 ? "text-red-400" : "text-slate-200")}>
                {formatCurrency(metrics.dailyLoss)}{" "}
                <span className="text-slate-500">/ {formatCurrency(metrics.configSnapshot.maxDailyLoss)}</span>
              </div>
            </div>
          </div>
          <RiskBar label="总仓位" ratio={metrics.totalPositionRatio} limit={metrics.configSnapshot.maxTotalPositionRatio} />
          <RiskBar label="最大单票" ratio={metrics.maxPositionRatio} limit={metrics.configSnapshot.maxPositionRatio} />
          <RiskBar label="单日亏损" ratio={metrics.dailyLossRatio} limit={1} warnAt={0.8} />
          <div className="flex flex-wrap gap-1.5 text-[10px] pt-1">
            <span className="text-slate-500">状态：</span>
            <span>集中度 <RiskBadge status={metrics.concentrationStatus} /></span>
            <span>个股止损 <RiskBadge status={metrics.stopLossStatus} /></span>
            <span>单日亏损 <RiskBadge status={metrics.dailyLossStatus} /></span>
          </div>
          {metrics.breaches.length > 0 && (
            <div className="rounded border border-red-500/40 bg-red-500/10 p-2 text-[11px] text-red-300 flex flex-col gap-1">
              <div className="flex items-center gap-1 font-semibold"><AlertTriangle className="w-3 h-3" /> 当前触发</div>
              {metrics.breaches.map((b, i) => (
                <div key={i}>· {b}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 2) 风控阈值配置 */}
      {config && (
        <ConfigForm config={config} onSave={handleSaveConfig} />
      )}

      {/* 3) 规则引擎 */}
      <div className="rounded border border-slate-700/60 p-2 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <ListChecks className="w-3 h-3" /> 规则引擎（{rules.length}）
          <button
            onClick={() => {
              setEditing(null);
              setShowRuleForm((v) => !v);
            }}
            className="ml-auto badge badge-cyan flex items-center gap-1 hover:opacity-80"
          >
            <Plus className="w-3 h-3" /> 新建规则
          </button>
        </div>

        {showRuleForm && (
          <RuleForm
            editing={editing}
            onCancel={() => {
              setShowRuleForm(false);
              setEditing(null);
            }}
            onCreate={handleCreateRule}
            onUpdate={handleUpdateRule}
          />
        )}

        <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
          {rules.length === 0 && <div className="text-[11px] text-slate-600">暂无规则，点击「新建规则」添加</div>}
          {rules.map((r) => (
            <div key={r.id} className="text-[11px] rounded bg-slate-800/40 px-2 py-1.5 flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => toggleRule(r)}
                  className={cn(
                    "w-9 text-[9px] rounded px-1 py-0.5 border",
                    r.enabled
                      ? "border-emerald-500/50 bg-emerald-900/20 text-emerald-300"
                      : "border-slate-600 text-slate-500",
                  )}
                  title={r.enabled ? "点击停用" : "点击启用"}
                >
                  {r.enabled ? "启用" : "停用"}
                </button>
                <span className="text-slate-200 font-medium">{r.name}</span>
                <span className="badge badge-gray text-[9px]">{RULE_TYPE_LABEL[r.ruleType] || r.ruleType}</span>
                <span
                  className={cn(
                    "badge text-[9px]",
                    r.severity === "critical" ? "badge-red" : r.severity === "high" ? "badge-orange" : "badge-yellow",
                  )}
                >
                  {SEVERITY_LABEL[r.severity] || r.severity}
                </span>
                <span className="ml-auto flex items-center gap-1">
                  <button
                    className="text-cyan-400 hover:text-cyan-300"
                    onClick={() => {
                      setEditing(r);
                      setShowRuleForm(true);
                    }}
                    title="编辑"
                  >
                    <SlidersHorizontal className="w-3 h-3" />
                  </button>
                  <button
                    className="text-red-400 hover:text-red-300"
                    onClick={() => handleDeleteRule(r.id)}
                    title="删除"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </span>
              </div>
              <div className="text-slate-500 text-[10px]">
                阈值 {r.threshold}
                {r.ruleType === "BLACKLIST" && r.detail?.codes
                  ? ` · 黑名单：${(r.detail.codes as string[]).join(", ")}`
                  : ""}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4) 风险事件 */}
      <div className="flex flex-col gap-1">
        <div className="text-[11px] text-slate-400 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> 风险事件（{events.length}）
          <button
            onClick={handleAckAll}
            className="ml-auto badge badge-gray flex items-center gap-1 hover:bg-slate-700"
            title="全部标记为已处理"
          >
            <CheckCheck className="w-3 h-3" /> 全部已读
          </button>
        </div>
        <div className="max-h-40 overflow-y-auto flex flex-col gap-1">
          {events.length === 0 && <div className="text-[11px] text-slate-600">暂无风险事件</div>}
          {events.map((ev) => (
            <div
              key={ev.id}
              className={cn(
                "text-[10px] rounded px-2 py-1 flex flex-col gap-0.5",
                ev.acked ? "bg-slate-800/20 opacity-60" : "bg-slate-800/40",
              )}
            >
              <div className="flex items-center gap-1">
                <RiskBadge
                  status={ev.level === "critical" || ev.level === "high" ? "breach" : ev.level}
                />
                <span className="text-slate-300">{ev.eventType}</span>
                {ev.code && <span className="text-slate-500 font-mono">{ev.code}</span>}
                <span className="ml-auto text-slate-600">{ev.createdAt.slice(5, 16)}</span>
                {!ev.acked && (
                  <button onClick={() => handleAck(ev.id)} className="text-cyan-400 hover:text-cyan-300" title="标记已读">
                    <Check className="w-3 h-3" />
                  </button>
                )}
              </div>
              <div className="text-slate-400">{ev.message}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 5) 风险报告 */}
      {report && (
        <div className="rounded border border-slate-700/60 p-2 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <FileText className="w-3 h-3" /> 风险报告
            <span className="ml-auto flex items-center gap-1">
              <RiskBadge status={report.overallStatus} />
              <span className="text-slate-300 font-mono">评分 {report.score}/100</span>
            </span>
          </div>
          <div className="text-[11px] text-slate-300">{report.summary}</div>
          {report.triggeredRules.length > 0 && (
            <div className="text-[10px] text-amber-300 flex flex-col gap-0.5">
              {report.triggeredRules.map((t, i) => (
                <div key={i}>· [{SEVERITY_LABEL[t.severity] || t.severity}] {t.name}：{t.message}</div>
              ))}
            </div>
          )}
          <div className="text-[10px] text-slate-400 flex flex-col gap-0.5">
            <span className="text-slate-500">处置建议：</span>
            {report.suggestions.map((s, i) => (
              <div key={i}>· {s}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// 风控阈值配置表单（复用 M5 字段）
// ============================================================
function ConfigForm({
  config,
  onSave,
}: {
  config: PaperRiskConfig;
  onSave: (patch: Partial<PaperRiskConfig>) => void;
}) {
  const [local, setLocal] = useState<PaperRiskConfig>(config);
  const set = (patch: Partial<PaperRiskConfig>) => setLocal((p) => ({ ...p, ...patch }));
  const inputCls =
    "bg-slate-800 rounded px-2 py-1 font-mono text-[12px] text-slate-200 border border-slate-700 focus:border-cyan-500/60 outline-none";

  return (
    <div className="rounded border border-slate-700/60 p-2 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-[11px] text-slate-400">
        <SlidersHorizontal className="w-3 h-3" /> 风控阈值
        <label className="ml-auto flex items-center gap-1 cursor-pointer">
          <input
            type="checkbox"
            checked={local.enabled}
            onChange={(e) => set({ enabled: e.target.checked })}
          />
          启用
        </label>
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <label className="flex flex-col gap-0.5">
          <span className="text-slate-500">单票上限(%)</span>
          <input
            type="number" step="1" min="0" max="100"
            className={inputCls}
            value={Math.round(local.maxPositionRatio * 100)}
            onChange={(e) => set({ maxPositionRatio: Math.max(0, Math.min(100, Number(e.target.value))) / 100 })}
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-slate-500">总仓位上限(%)</span>
          <input
            type="number" step="1" min="0" max="100"
            className={inputCls}
            value={Math.round(local.maxTotalPositionRatio * 100)}
            onChange={(e) => set({ maxTotalPositionRatio: Math.max(0, Math.min(100, Number(e.target.value))) / 100 })}
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-slate-500">单笔上限(元)</span>
          <input
            type="number" step="1000" min="0"
            className={inputCls}
            value={local.maxSingleAmount}
            onChange={(e) => set({ maxSingleAmount: Math.max(0, Number(e.target.value)) })}
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-slate-500">单日亏损上限(元)</span>
          <input
            type="number" step="1000" min="0"
            className={inputCls}
            value={local.maxDailyLoss}
            onChange={(e) => set({ maxDailyLoss: Math.max(0, Number(e.target.value)) })}
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-slate-500">个股止损线(%)</span>
          <input
            type="number" step="1" min="0" max="100"
            className={inputCls}
            value={Math.round(local.stopLossRatio * 100)}
            onChange={(e) => set({ stopLossRatio: Math.max(0, Math.min(100, Number(e.target.value))) / 100 })}
          />
        </label>
        <label className="flex items-center gap-1 pt-4 cursor-pointer">
          <input
            type="checkbox"
            checked={local.allowShort}
            onChange={(e) => set({ allowShort: e.target.checked })}
          />
          <span className="text-slate-400">允许卖空</span>
        </label>
      </div>
      <button
        onClick={() =>
          onSave({
            enabled: local.enabled,
            maxPositionRatio: local.maxPositionRatio,
            maxTotalPositionRatio: local.maxTotalPositionRatio,
            maxSingleAmount: local.maxSingleAmount,
            maxDailyLoss: local.maxDailyLoss,
            stopLossRatio: local.stopLossRatio,
            allowShort: local.allowShort,
          })
        }
        className="mt-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-[11px] py-1.5"
      >
        保存风控参数
      </button>
    </div>
  );
}

// ============================================================
// 规则编辑/新建表单
// ============================================================
function RuleForm({
  editing,
  onCancel,
  onCreate,
  onUpdate,
}: {
  editing: PaperRiskRule | null;
  onCancel: () => void;
  onCreate: (body: Parameters<typeof createPaperRiskRule>[1]) => void;
  onUpdate: (ruleId: number, body: Parameters<typeof updatePaperRiskRule>[2]) => void;
}) {
  const [name, setName] = useState(editing?.name ?? "");
  const [ruleType, setRuleType] = useState<PaperRiskRuleType>(editing?.ruleType ?? "BLACKLIST");
  const [threshold, setThreshold] = useState(editing?.threshold ?? 0);
  const [severity, setSeverity] = useState(editing?.severity ?? "warn");
  const [codes, setCodes] = useState(
    editing?.ruleType === "BLACKLIST" && editing.detail?.codes
      ? (editing.detail.codes as string[]).join(", ")
      : "",
  );
  const inputCls =
    "w-full bg-slate-800 rounded px-2 py-1.5 text-[12px] font-mono text-slate-200 border border-slate-700 focus:border-cyan-500/60 outline-none";

  const submit = () => {
    if (!name.trim()) return;
    const detail: Record<string, unknown> = {};
    if (ruleType === "BLACKLIST") {
      detail.codes = codes
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);
    }
    const body = {
      name: name.trim(),
      ruleType,
      threshold: Number(threshold) || 0,
      severity,
      detail,
    };
    if (editing) onUpdate(editing.id, body);
    else onCreate(body);
  };

  return (
    <div className="rounded border border-cyan-700/40 bg-slate-900/40 p-2 flex flex-col gap-2">
      <div className="text-[11px] text-cyan-300">{editing ? "编辑规则" : "新建规则"}</div>
      <input className={inputCls} placeholder="规则名称（如：白酒板块限仓）" value={name} onChange={(e) => setName(e.target.value)} />
      <div className="grid grid-cols-2 gap-2">
        <select className={cn(inputCls, "font-sans")} value={ruleType} onChange={(e) => setRuleType(e.target.value as PaperRiskRuleType)}>
          {(Object.keys(RULE_TYPE_LABEL) as PaperRiskRuleType[]).map((k) => (
            <option key={k} value={k}>{RULE_TYPE_LABEL[k]}</option>
          ))}
        </select>
        <select className={cn(inputCls, "font-sans")} value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="warn">提示</option>
          <option value="high">重要</option>
          <option value="critical">严重</option>
        </select>
      </div>
      {ruleType === "BLACKLIST" ? (
        <input
          className={inputCls}
          placeholder="黑名单代码，逗号分隔（如 600519, 000858）"
          value={codes}
          onChange={(e) => setCodes(e.target.value)}
        />
      ) : (
        <label className="flex flex-col gap-0.5 text-[10px] text-slate-500">
          阈值（% 或倍数）
          <input className={inputCls} type="number" step="1" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
        </label>
      )}
      <div className="flex gap-2 pt-1">
        <button onClick={submit} className="btn-primary flex-1 text-[12px]">
          {editing ? "保存修改" : "创建规则"}
        </button>
        <button onClick={onCancel} className="btn-secondary text-[12px]">取消</button>
      </div>
    </div>
  );
}
