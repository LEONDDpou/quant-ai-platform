"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, Search, Play, Trophy } from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { StrategyCard, type StrategyCardData } from "@/components/ui/StrategyCard";
import { StrategyReport } from "@/components/ui/StrategyReport";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import {
  fetchStrategies,
  deleteStrategy,
  archiveStrategy,
  toggleStrategyApi,
  type ApiStrategy,
} from "@/lib/api";
import { strategies as mockStrategies } from "@/lib/mock-data";

// 确定性曲线（避免 Math.random 导致的 hydration 错乱），仅用作回撤对比基准/兜底
function buildCurve(seedStr: string, annual: number, n = 30): number[] {
  let seed = 0;
  for (const ch of seedStr) seed += ch.charCodeAt(0);
  const out: number[] = [];
  let prev = 100;
  const drift = (annual / 100) / n;
  for (let i = 0; i < n; i++) {
    const r = Math.sin((i + 1) * 12.9898 + seed * 0.013) * 43758.5453;
    const rand = r - Math.floor(r);
    prev = Number((prev * (1 + drift) + (rand - 0.5) * 4).toFixed(2));
    out.push(prev);
  }
  return out;
}

// 后端策略 → 前端卡片数据
function mapApi(s: ApiStrategy): StrategyCardData {
  return {
    id: s.id,
    name: s.name,
    type: s.type,
    status: s.status,
    annualizedReturn: s.annualizedReturn,
    maxDrawdown: s.maxDrawdown,
    winRate: s.winRate,
    sharpeRatio: s.sharpeRatio,
    description: s.description,
    tags: [],
    equityCurve: (s.equityCurve ?? []).map((p) => p.value),
    tradesCount: s.totalTrades,
    pnlAmount: undefined,
  };
}

// 风险等级（基于回撤 + 夏普派生；后端无独立风险字段）
type RiskLevel = "low" | "mid" | "high";
function riskLevel(s: StrategyCardData): RiskLevel {
  if (s.maxDrawdown >= 15 || (s.sharpeRatio ?? 99) < 2.0) return "high";
  if (s.maxDrawdown >= 10 || (s.sharpeRatio ?? 99) < 2.5) return "mid";
  return "low";
}

// 真实状态维度，避免原「回撤中」筛选语义误导
const filterTabs = [
  { key: "all", label: "全部" },
  { key: "running", label: "运行中" },
  { key: "stopped", label: "已停止" },
  { key: "backtesting", label: "回测中" },
  { key: "archived", label: "已归档" },
];

const STRATEGY_TYPES = [
  "机器学习策略",
  "AI预测策略",
  "量化因子策略",
  "事件驱动策略",
  "技术指标策略",
];

export default function StrategiesPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [strategies, setStrategies] = useState<StrategyCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [range, setRange] = useState<"3M" | "6M" | "1Y">("3M");
  // P2: 排序 + 风险筛选
  const [sort, setSort] = useState<"default" | "return" | "sharpe" | "drawdown" | "winRate" | "risk">("default");
  const [riskFilter, setRiskFilter] = useState<"all" | "high">("all");
  // 表单：创建 / 编辑
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", type: STRATEGY_TYPES[0], annualizedReturn: 15, maxDrawdown: 8, winRate: 60 });
  // 报告弹窗（已合并原「详情」弹窗）
  const [reportId, setReportId] = useState<string | null>(null);
  // 静态部署（无后端 API）时回退到本地 mock 数据
  const [usingMock, setUsingMock] = useState(false);

  const load = useCallback((showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    fetchStrategies()
      .then((data) => { setStrategies(data.map(mapApi)); setUsingMock(false); })
      .catch((e: unknown) => {
        // 静态部署（无后端 API）时回退到本地 mock，保证页面可看
        setStrategies((mockStrategies as unknown as ApiStrategy[]).map(mapApi));
        setUsingMock(true);
        setError(null);
      })
      .finally(() => { if (showLoading) setLoading(false); });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // P2: 自动轮询刷新（静默，不闪 loading）
  useEffect(() => {
    const t = setInterval(() => load(false), 30000);
    return () => clearInterval(t);
  }, [load]);

  const filtered = strategies
    .filter((s) => {
      if (filter !== "all" && s.status !== filter) return false;
      if (search && !s.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (riskFilter === "high" && riskLevel(s) !== "high") return false;
      return true;
    })
    .sort((a, b) => {
      switch (sort) {
        case "return": return b.annualizedReturn - a.annualizedReturn;
        case "sharpe": return (b.sharpeRatio ?? 0) - (a.sharpeRatio ?? 0);
        case "drawdown": return a.maxDrawdown - b.maxDrawdown; // 回撤小更好
        case "winRate": return b.winRate - a.winRate;
        case "risk": {
          const order = { high: 3, mid: 2, low: 1 } as const;
          return order[riskLevel(b)] - order[riskLevel(a)];
        }
        default: return 0;
      }
    });

  const runningCount = strategies.filter((s) => s.status === "running").length;
  const stoppedCount = strategies.filter((s) => s.status === "stopped").length;
  const totalTrades = strategies.reduce((sum, s) => sum + (s.tradesCount || 0), 0);
  // 累计收益（万元）：基于真实净值曲线首尾差值求和
  const cumPnlYuan = strategies.reduce((sum, s) => {
    const c = s.equityCurve;
    if (c && c.length > 1) sum += c[c.length - 1] - c[0];
    return sum;
  }, 0);
  const cumPnlWan = cumPnlYuan / 10000;

  const toggleStrategy = async (id: string) => {
    try {
      const r = await toggleStrategyApi(id);
      setStrategies((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: r.status as StrategyCardData["status"] } : s))
      );
      toast(r.message, "success");
    } catch (e) {
      toast("操作失败：" + (e instanceof Error ? e.message : "未知错误"), "error");
    }
  };

  const handleDelete = async (id: string) => {
    if (typeof window !== "undefined" && !window.confirm("确认删除该策略？此操作不可恢复。")) return;
    try {
      await deleteStrategy(id);
      setStrategies((prev) => prev.filter((s) => s.id !== id));
      if (reportId === id) setReportId(null);
      toast("策略已删除", "success");
    } catch (e) {
      toast("删除失败：" + (e instanceof Error ? e.message : "未知错误"), "error");
    }
  };

  const handleArchive = async (id: string) => {
    try {
      await archiveStrategy(id);
      setStrategies((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: "archived" } : s))
      );
      toast("策略已归档", "success");
    } catch (e) {
      toast("归档失败：" + (e instanceof Error ? e.message : "未知错误"), "error");
    }
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: "", type: STRATEGY_TYPES[0], annualizedReturn: 15, maxDrawdown: 8, winRate: 60 });
    setFormOpen(true);
  };

  const openEdit = (id: string) => {
    const s = strategies.find((x) => x.id === id);
    if (!s) return;
    setEditingId(id);
    setForm({ name: s.name, type: s.type, annualizedReturn: s.annualizedReturn, maxDrawdown: s.maxDrawdown, winRate: s.winRate });
    setFormOpen(true);
  };

  const submitForm = () => {
    if (!form.name.trim()) {
      toast("请填写策略名称", "error");
      return;
    }
    if (editingId) {
      setStrategies((prev) =>
        prev.map((s) =>
          s.id === editingId
            ? {
                ...s,
                name: form.name,
                type: form.type,
                annualizedReturn: form.annualizedReturn,
                maxDrawdown: form.maxDrawdown,
                winRate: form.winRate,
                equityCurve: buildCurve(editingId + form.name, form.annualizedReturn),
              }
            : s
        )
      );
      toast("策略已更新", "success");
    } else {
      const id = `strat-${Date.now()}`;
      const newS: StrategyCardData = {
        id,
        name: form.name,
        type: form.type,
        status: "stopped",
        annualizedReturn: form.annualizedReturn,
        maxDrawdown: form.maxDrawdown,
        winRate: form.winRate,
        sharpeRatio: Number((form.winRate / 25).toFixed(2)),
        tags: [form.type.slice(0, 2)],
        description: "用户新建策略，等待回测与上线验证",
        pnlAmount: "¥0",
        tradesCount: 0,
        equityCurve: buildCurve(id, form.annualizedReturn),
      };
      setStrategies((prev) => [newS, ...prev]);
      toast("策略已创建（已停止，待回测）", "success");
    }
    setFormOpen(false);
    setEditingId(null);
  };

  const onBacktest = (id: string) => {
    const s = strategies.find((x) => x.id === id);
    toast(`已跳转回测：${s?.name ?? id}`, "info");
    router.push("/backtest");
  };

  // 支持通过分享链接 ?report=<id> 自动打开报告（仅首次自动打开）
  const autoOpened = useRef(false);
  useEffect(() => {
    if (typeof window === "undefined" || autoOpened.current) return;
    const id = new URLSearchParams(window.location.search).get("report");
    if (id && strategies.some((s) => s.id === id)) {
      setReportId(id);
      autoOpened.current = true;
    }
  }, [strategies]);

  const reportStrategy = strategies.find((s) => s.id === reportId) || null;

  // ===== 对比图（真实净值曲线，归一化）=====
  const rangePts = range === "3M" ? 30 : range === "6M" ? 60 : 120;
  const sliceCurve = (vals: number[] | undefined, n: number): number[] => {
    if (!vals || vals.length === 0) return [];
    const slice = vals.slice(-n);
    const base = slice[0] || 1;
    return slice.map((v) => Number(((v / base) * 100).toFixed(2)));
  };
  const comparisonOption: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 30, right: 16, bottom: 24, left: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    legend: { top: 0, textStyle: { color: "#8b9bb4", fontSize: 10 }, itemWidth: 14, itemHeight: 8 },
    xAxis: { type: "category", data: Array.from({ length: rangePts }, (_, i) => `${i + 1}`), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { show: false } },
    yAxis: { type: "value", scale: true, axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 9 } },
    series: [
      ...filtered.slice(0, 4).map((s, i) => {
        const real = sliceCurve(s.equityCurve, rangePts);
        return {
          name: s.name.slice(0, 8),
          type: "line" as const,
          data: real.length ? real : buildCurve(s.id + s.name, s.annualizedReturn, rangePts),
          smooth: true,
          symbol: "none" as const,
          lineStyle: { width: 1.5, color: ["#22d3ee", "#34d399", "#fbbf24", "#a78bfa"][i % 4] },
        };
      }),
      {
        name: "沪深300",
        type: "line" as const,
        data: buildCurve("hs300-benchmark", 6.5, rangePts),
        smooth: true,
        symbol: "none" as const,
        lineStyle: { width: 1.5, type: "dashed" as const, color: "#64748b" },
      },
    ],
  };

  return (
    <div className="space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">AI策略中心</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            基于AI驱动的多策略管理平台 · 智能调度 · 实时监控 · 风险预警
          </p>
          <div className="mt-2 flex items-center gap-3 text-xs">
            {usingMock ? (
              <span className="flex items-center gap-1 text-amber-400">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> 静态演示数据 · 本地 Mock
              </span>
            ) : (
              <span className="flex items-center gap-1 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-glow" /> 实时数据 · 后端 API
              </span>
            )}
            <button onClick={() => load()} className="text-slate-500 hover:text-slate-300 underline-offset-2 hover:underline">
              刷新
            </button>
            {loading && <span className="text-slate-500">加载中…</span>}
          </div>
        </div>
        <Link
          href="/strategy-market"
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[#1e2a3d] text-xs text-slate-300 hover:text-cyan-300 hover:border-cyan-500/40 transition-colors"
        >
          <Trophy className="w-4 h-4" />
          完整榜单
        </Link>
        <button onClick={openCreate} className="btn-primary flex items-center gap-1.5">
          <Plus className="w-4 h-4" />
          创建新策略
        </button>
      </div>

      {usingMock && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300/90">
          静态部署模式：未检测到后端 API，当前展示本地 Mock 演示数据（策略收益、回撤、净值曲线均为模拟值），仅用于功能展示，不构成任何投资建议。
        </div>
      )}

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="card-flat flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <Play className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <div className="font-mono font-bold text-lg text-emerald-400">{runningCount}</div>
            <div className="text-[11px] text-slate-500">个运行中</div>
          </div>
          <span className="badge badge-running ml-auto cursor-pointer" onClick={() => setFilter("running")}>查看</span>
        </div>

        <div className="card-flat flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
          <div>
            <div className={cn("font-mono font-bold text-lg", cumPnlWan >= 0 ? "text-emerald-400" : "text-rose-400")}>
              {cumPnlWan >= 0 ? "+" : ""}
              {cumPnlWan.toFixed(2)}
            </div>
            <div className="text-[11px] text-slate-500">累计收益(万元)</div>
          </div>
        </div>

        <div className="card-flat flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <div className="font-mono font-bold text-lg text-amber-400">{stoppedCount}</div>
            <div className="text-[11px] text-slate-500">个已停止</div>
          </div>
          <span className="badge badge-gray ml-auto cursor-pointer" onClick={() => setFilter("stopped")}>查看</span>
        </div>

        <div className="card-flat flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <div className="font-mono font-bold text-lg text-violet-300">{totalTrades.toLocaleString()}</div>
            <div className="text-[11px] text-slate-500">总交易次数</div>
          </div>
        </div>
      </div>

      {/* Search + Filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索策略名称..."
            className="input-dark pl-9"
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)}
          className="input-dark text-xs py-1.5 cursor-pointer"
        >
          <option value="default">默认排序</option>
          <option value="return">年化收益 ↓</option>
          <option value="sharpe">夏普比率 ↓</option>
          <option value="drawdown">最大回撤 ↑</option>
          <option value="winRate">胜率 ↓</option>
          <option value="risk">风险等级 ↓</option>
        </select>
        <button
          onClick={() => setRiskFilter(riskFilter === "high" ? "all" : "high")}
          className={cn(
            "px-3 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap",
            riskFilter === "high" ? "bg-rose-500/20 text-rose-300" : "text-slate-500 hover:text-slate-300"
          )}
        >仅看高风险</button>
        <div className="flex items-center bg-[#111827] rounded-lg p-0.5 border border-[#1e2a3d]">
          {filterTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                filter === tab.key ? "bg-[#1e293b] text-slate-200 shadow-sm" : "text-slate-500 hover:text-slate-300"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="card p-6 text-center">
          <p className="text-rose-400 text-sm">加载失败：{error}</p>
          <button onClick={() => load()} className="btn-primary text-xs mt-3">重试</button>
        </div>
      )}

      {/* Strategy Grid */}
      {!error && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((s, idx) => (
            <StrategyCard
              key={s.id}
              strategy={s}
              risk={riskLevel(s)}
              rank={sort !== "default" ? idx + 1 : undefined}
              onToggle={toggleStrategy}
              onView={(id) => setReportId(id)}
              onEdit={(id) => openEdit(id)}
              onBacktest={(id) => onBacktest(id)}
              onArchive={(id) => handleArchive(id)}
              onDelete={(id) => handleDelete(id)}
            />
          ))}
        </div>
      )}

      {!error && filtered.length === 0 && (
        <div className="text-center py-16 text-slate-600">
          <p>{loading ? "加载中…" : "没有匹配的策略"}</p>
        </div>
      )}

      {/* Bottom: Strategy Comparison Chart */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title">策略净值对比 · 基准 沪深300</h2>
          <div className="flex items-center gap-1">
            {(["3M", "6M", "1Y"] as const).map((label) => (
              <button key={label} onClick={() => setRange(label)} className={cn(
                "px-2 py-0.5 text-[10px] rounded transition-colors",
                range === label ? "bg-[#1e293b] text-slate-300" : "text-slate-600 hover:text-slate-400"
              )}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <ReactECharts option={comparisonOption} style={{ height: "260px", width: "100%" }} />
      </div>

      {/* 创建 / 编辑 弹窗 */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingId ? "编辑策略" : "创建新策略"}
        footer={
          <>
            <button className="btn-ghost text-xs" onClick={() => setFormOpen(false)}>取消</button>
            <button className="btn-primary text-xs" onClick={submitForm}>
              {editingId ? "保存修改" : "创建策略"}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">策略名称</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="例如：低波因子轮动 v1.0"
              className="input-dark w-full"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1.5 block">策略类型</label>
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="input-dark w-full"
            >
              {STRATEGY_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">年化收益 %</label>
              <input
                type="number"
                value={form.annualizedReturn}
                onChange={(e) => setForm({ ...form, annualizedReturn: Number(e.target.value) })}
                className="input-dark w-full font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">最大回撤 %</label>
              <input
                type="number"
                value={form.maxDrawdown}
                onChange={(e) => setForm({ ...form, maxDrawdown: Number(e.target.value) })}
                className="input-dark w-full font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">胜率 %</label>
              <input
                type="number"
                value={form.winRate}
                onChange={(e) => setForm({ ...form, winRate: Number(e.target.value) })}
                className="input-dark w-full font-mono"
              />
            </div>
          </div>
        </div>
      </Modal>

      {/* 策略报告（合并原「详情」弹窗） */}
      <StrategyReport
        strategy={reportStrategy}
        open={reportId !== null}
        onClose={() => setReportId(null)}
        onEdit={(id) => { setReportId(null); openEdit(id); }}
        onBacktest={(id) => onBacktest(id)}
        onArchive={(id) => handleArchive(id)}
        onDelete={(id) => handleDelete(id)}
      />
    </div>
  );
}
