"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, ArrowUpDown, ArrowUp, ArrowDown, Brain } from "lucide-react";
import { StrategyReport } from "@/components/ui/StrategyReport";
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

// 后端策略 → 前端卡片数据（与 /strategies 同源映射）
function mapApi(s: ApiStrategy) {
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
    tags: [] as string[],
    equityCurve: (s.equityCurve ?? []).map((p) => p.value),
    tradesCount: s.totalTrades,
    pnlAmount: undefined as string | undefined,
  };
}
type StrategyRow = ReturnType<typeof mapApi>;

// 风险等级（基于回撤 + 夏普派生；后端无独立风险字段，与 /strategies 同源）
type RiskLevel = "low" | "mid" | "high";
function riskLevel(s: StrategyRow): RiskLevel {
  if (s.maxDrawdown >= 15 || (s.sharpeRatio ?? 99) < 2.0) return "high";
  if (s.maxDrawdown >= 10 || (s.sharpeRatio ?? 99) < 2.5) return "mid";
  return "low";
}
const riskMeta: Record<RiskLevel, { label: string; cls: string }> = {
  low: { label: "低风险", cls: "text-emerald-400" },
  mid: { label: "中风险", cls: "text-amber-400" },
  high: { label: "高风险", cls: "text-rose-400" },
};

const statusMeta: Record<string, { label: string; cls: string }> = {
  running: { label: "运行中", cls: "text-emerald-400 bg-emerald-500/10" },
  stopped: { label: "已停止", cls: "text-slate-400 bg-slate-500/10" },
  backtesting: { label: "回测中", cls: "text-cyan-400 bg-cyan-500/10" },
  paused: { label: "已暂停", cls: "text-amber-400 bg-amber-500/10" },
  archived: { label: "已归档", cls: "text-slate-500 bg-slate-600/10" },
};

type SortKey = "name" | "return" | "sharpe" | "drawdown" | "winRate" | "risk";

export default function StrategyMarketPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [rows, setRows] = useState<StrategyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskOnly, setRiskOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("return");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [reportId, setReportId] = useState<string | null>(null);
  // 静态部署（无后端 API）时回退到本地 mock 数据
  const [usingMock, setUsingMock] = useState(false);

  const load = useCallback((showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    fetchStrategies()
      .then((data) => { setRows(data.map(mapApi)); setUsingMock(false); })
      .catch((e: unknown) => {
        // 静态部署（无后端 API）时回退到本地 mock，保证页面可看
        setRows((mockStrategies as unknown as ApiStrategy[]).map(mapApi));
        setUsingMock(true);
        setError(null);
      })
      .finally(() => {
        if (showLoading) setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // 自动轮询（静默）
  useEffect(() => {
    const t = setInterval(() => load(false), 30000);
    return () => clearInterval(t);
  }, [load]);

  // 支持 ?report=<id> 自动打开
  const autoOpened = useRef(false);
  useEffect(() => {
    if (typeof window === "undefined" || autoOpened.current) return;
    const id = new URLSearchParams(window.location.search).get("report");
    if (id && rows.some((r) => r.id === id)) {
      setReportId(id);
      autoOpened.current = true;
    }
  }, [rows]);

  const filtered = rows.filter((r) => {
    if (statusFilter !== "all" && r.status !== statusFilter) return false;
    if (riskOnly && riskLevel(r) !== "high") return false;
    if (search && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    let cmp = 0;
    switch (sortKey) {
      case "name":
        cmp = a.name.localeCompare(b.name, "zh");
        break;
      case "return":
        cmp = a.annualizedReturn - b.annualizedReturn;
        break;
      case "sharpe":
        cmp = (a.sharpeRatio ?? 0) - (b.sharpeRatio ?? 0);
        break;
      case "drawdown":
        cmp = a.maxDrawdown - b.maxDrawdown;
        break;
      case "winRate":
        cmp = a.winRate - b.winRate;
        break;
      case "risk": {
        const order = { high: 3, mid: 2, low: 1 } as const;
        cmp = order[riskLevel(a)] - order[riskLevel(b)];
        break;
      }
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  const onSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "name" ? "asc" : "desc");
    }
  };

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? <ArrowUp className="inline w-3 h-3" /> : <ArrowDown className="inline w-3 h-3" />) : <ArrowUpDown className="inline w-3 h-3 opacity-30" />;

  const handleDelete = async (id: string) => {
    if (typeof window !== "undefined" && !window.confirm("确认删除该策略？此操作不可恢复。")) return;
    try {
      await deleteStrategy(id);
      setRows((prev) => prev.filter((r) => r.id !== id));
      if (reportId === id) setReportId(null);
      toast("策略已删除", "success");
    } catch (e) {
      toast("删除失败：" + (e instanceof Error ? e.message : "未知错误"), "error");
    }
  };

  const handleArchive = async (id: string) => {
    try {
      await archiveStrategy(id);
      setRows((prev) => prev.map((r) => (r.id === id ? { ...r, status: "archived" } : r)));
      toast("策略已归档", "success");
    } catch (e) {
      toast("归档失败：" + (e instanceof Error ? e.message : "未知错误"), "error");
    }
  };

  const handleToggle = async (id: string) => {
    try {
      const r = await toggleStrategyApi(id);
      setRows((prev) => prev.map((x) => (x.id === id ? { ...x, status: r.status as StrategyRow["status"] } : x)));
      toast(r.message, "success");
    } catch (e) {
      toast("操作失败：" + (e instanceof Error ? e.message : "未知错误"), "error");
    }
  };

  const reportRow = rows.find((r) => r.id === reportId) || null;

  const fmtPct = (v: number, withSign = true) =>
    `${withSign && v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

  return (
    <div className="space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold text-slate-100">策略市场 · 全量排行</h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            多维度绩效排行 · 点击表头排序 · 点行查看报告 ·{" "}
            <Link href="/strategies" className="text-cyan-400 hover:underline">
              返回策略中心
            </Link>
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
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
        </div>
      </div>

      {/* 演示数据提示 */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300/90">
        {usingMock
          ? "静态部署模式：未检测到后端 API，当前展示本地 Mock 演示数据（策略收益、回撤、净值曲线均为模拟值），仅用于功能展示，不构成任何投资建议。"
          : "演示数据提示：策略收益、回撤、净值曲线均为后端 Mock 演示数据，仅用于功能展示，不构成任何投资建议。"}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
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
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="input-dark text-xs py-1.5 cursor-pointer"
        >
          <option value="all">全部状态</option>
          <option value="running">运行中</option>
          <option value="stopped">已停止</option>
          <option value="backtesting">回测中</option>
          <option value="archived">已归档</option>
        </select>
        <button
          onClick={() => setRiskOnly((v) => !v)}
          className={cn(
            "px-3 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap",
            riskOnly ? "bg-rose-500/20 text-rose-300" : "text-slate-500 hover:text-slate-300"
          )}
        >
          仅看高风险
        </button>
        {loading && <span className="text-slate-500">加载中…</span>}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {error ? (
          <div className="p-8 text-center">
            <p className="text-rose-400 text-sm">加载失败：{error}</p>
            <button onClick={() => load()} className="btn-primary text-xs mt-3">重试</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead>
                <tr className="text-[11px] text-slate-500 border-b border-[#151d2e]">
                  <th className="text-left font-medium px-3 py-2.5 w-12">#</th>
                  <th className="text-left font-medium px-3 py-2.5 cursor-pointer select-none hover:text-slate-300" onClick={() => onSort("name")}>
                    策略 {arrow("name")}
                  </th>
                  <th className="text-left font-medium px-3 py-2.5">类型</th>
                  <th className="text-right font-medium px-3 py-2.5 cursor-pointer select-none hover:text-slate-300" onClick={() => onSort("return")}>
                    年化收益 {arrow("return")}
                  </th>
                  <th className="text-right font-medium px-3 py-2.5 cursor-pointer select-none hover:text-slate-300" onClick={() => onSort("sharpe")}>
                    夏普 {arrow("sharpe")}
                  </th>
                  <th className="text-right font-medium px-3 py-2.5 cursor-pointer select-none hover:text-slate-300" onClick={() => onSort("drawdown")}>
                    最大回撤 {arrow("drawdown")}
                  </th>
                  <th className="text-right font-medium px-3 py-2.5 cursor-pointer select-none hover:text-slate-300" onClick={() => onSort("winRate")}>
                    胜率 {arrow("winRate")}
                  </th>
                  <th className="text-left font-medium px-3 py-2.5 cursor-pointer select-none hover:text-slate-300" onClick={() => onSort("risk")}>
                    风险 {arrow("risk")}
                  </th>
                  <th className="text-left font-medium px-3 py-2.5">状态</th>
                  <th className="text-right font-medium px-3 py-2.5">操作</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r, i) => {
                  const rl = riskLevel(r);
                  const sm = statusMeta[r.status] || statusMeta.stopped;
                  return (
                    <tr
                      key={r.id}
                      onClick={() => setReportId(r.id)}
                      className="border-b border-[#101724] hover:bg-[#0f1626] cursor-pointer transition-colors"
                    >
                      <td className="px-3 py-3 font-mono text-slate-500">{i + 1}</td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-slate-200">{r.name}</div>
                        <div className="text-[10px] text-slate-600">{r.id}</div>
                      </td>
                      <td className="px-3 py-3 text-xs text-slate-400">{r.type}</td>
                      <td className={cn("px-3 py-3 text-right font-mono", r.annualizedReturn >= 0 ? "text-emerald-400" : "text-rose-400")}>
                        {fmtPct(r.annualizedReturn)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">{(r.sharpeRatio ?? 0).toFixed(2)}</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">{r.maxDrawdown.toFixed(1)}%</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">{r.winRate.toFixed(1)}%</td>
                      <td className={cn("px-3 py-3 text-xs font-medium", riskMeta[rl].cls)}>
                        {rl === "high" ? (
                          <span
                            className="inline-flex items-center gap-1 cursor-pointer hover:underline"
                            onClick={(e) => {
                              e.stopPropagation();
                              router.push("/dashboard");
                            }}
                            title="查看风险监控"
                          >
                            {riskMeta[rl].label}
                          </span>
                        ) : (
                          riskMeta[rl].label
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <span className={cn("text-[10px] px-2 py-0.5 rounded-full", sm.cls)}>{sm.label}</span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setReportId(r.id);
                          }}
                          className="text-xs text-cyan-400 hover:underline"
                        >
                          查看
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {sorted.length === 0 && (
                  <tr>
                    <td colSpan={10} className="px-3 py-12 text-center text-slate-600">
                      {loading ? "加载中…" : "没有匹配的策略"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <StrategyReport
        strategy={reportRow as any}
        open={reportId !== null}
        onClose={() => setReportId(null)}
        onEdit={(id) => {
          setReportId(null);
          router.push("/strategies?report=" + id);
        }}
        onBacktest={(id) => {
          setReportId(null);
          router.push("/backtest");
        }}
        onArchive={(id) => handleArchive(id)}
        onDelete={(id) => handleDelete(id)}
      />
    </div>
  );
}
