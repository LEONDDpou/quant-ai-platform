"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Building2,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  BarChart3,
  RefreshCw,
  ArrowUp,
  ArrowDown,
  Flame,
  Shield,
  Layers,
  Loader2,
  Zap,
  Globe,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getInstitutionAggregate,
  type InstitutionAggregate,
  type LhbEntry,
} from "@/lib/api";
import StockDetailPanel from "@/components/stock/StockDetailPanel";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";

// ============================================================
// 工具函数
// ============================================================
function formatPct(v: number): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function formatFlow(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(1)}亿`;
  if (abs >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
}

// ============================================================
// 子组件：机构活跃度仪表
// ============================================================
function ActivityGauge({
  score,
  level,
  lhbCount,
  mainDirection,
  mainIntensity,
  mainFlow5d,
  mainFlow20d,
}: {
  score: number;
  level: string;
  lhbCount: number;
  mainDirection: string;
  mainIntensity: number;
  mainFlow5d: number;
  mainFlow20d: number;
}) {
  const barColor =
    score >= 60
      ? "bg-gradient-to-r from-emerald-500 to-cyan-400"
      : score >= 30
        ? "bg-gradient-to-r from-amber-500 to-yellow-400"
        : "bg-gradient-to-r from-slate-600 to-slate-500";

  const ringColor =
    score >= 60
      ? "text-emerald-400"
      : score >= 30
        ? "text-amber-400"
        : "text-slate-500";

  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Activity className="w-4 h-4 text-fuchsia-400" />
        <span className="text-sm font-bold text-slate-200">机构交易活跃度</span>
      </div>
      <div className="p-5 flex flex-col items-center">
        {/* 圆环百分比 */}
        <div className="relative w-32 h-32 mb-3">
          <svg className="w-full h-full" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" stroke="#151d2e" strokeWidth="8" />
            <circle
              cx="60" cy="60" r="52"
              fill="none"
              stroke="currentColor"
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${(score / 100) * 327} 327`}
              transform="rotate(-90 60 60)"
              className={ringColor}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold font-mono text-slate-100">{score.toFixed(0)}</span>
            <span className="text-[10px] text-slate-500">/ 100</span>
          </div>
        </div>

        <span
          className={cn(
            "badge text-[11px] mb-4 px-3 py-1",
            level === "活跃"
              ? "badge-green"
              : level === "温和"
                ? "badge-yellow"
                : "bg-slate-500/10 text-slate-400 border border-slate-500/20 rounded-full px-2.5 py-0.5 text-[11px]",
          )}
        >
          {level}
        </span>

        <div className="w-full grid grid-cols-2 gap-3 text-center">
          <div className="bg-[#0d1220] rounded-lg p-2.5">
            <div className="text-[9px] text-slate-600 mb-0.5">龙虎榜活跃度</div>
            <div className="text-sm font-mono font-bold text-amber-400">{lhbCount} 只</div>
          </div>
          <div className="bg-[#0d1220] rounded-lg p-2.5">
            <div className="text-[9px] text-slate-600 mb-0.5">主力方向</div>
            <div
              className={cn(
                "text-sm font-mono font-bold",
                mainDirection === "流入" ? "text-red-400" : "text-green-400",
              )}
            >
              {mainDirection}
            </div>
          </div>
          <div className="bg-[#0d1220] rounded-lg p-2.5">
            <div className="text-[9px] text-slate-600 mb-0.5">5日主力</div>
            <div
              className={cn(
                "text-xs font-mono font-medium",
                mainFlow5d > 0 ? "text-red-400" : "text-green-400",
              )}
            >
              {formatFlow(mainFlow5d)}
            </div>
          </div>
          <div className="bg-[#0d1220] rounded-lg p-2.5">
            <div className="text-[9px] text-slate-600 mb-0.5">20日主力</div>
            <div
              className={cn(
                "text-xs font-mono font-medium",
                mainFlow20d > 0 ? "text-red-400" : "text-green-400",
              )}
            >
              {formatFlow(mainFlow20d)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：北向资金
// ============================================================
function NorthboundCard({
  today,
  todayDesc,
}: {
  today: number;
  todayDesc: string;
}) {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Globe className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-bold text-slate-200">北向资金</span>
        <span className="text-[10px] text-slate-600 ml-auto">沪股通 + 深股通</span>
      </div>
      <div className="p-5 flex flex-col items-center">
        <div
          className={cn(
            "text-3xl font-bold font-mono mb-1",
            today > 0 ? "text-red-400" : today < 0 ? "text-green-400" : "text-slate-400",
          )}
        >
          {todayDesc}
        </div>
        <span className="text-[11px] text-slate-500 mb-4">今日北向资金净流向</span>
        <div className="w-full bg-[#0d1220] rounded-lg p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">北向趋势判断</span>
            <span
              className={cn(
                "font-medium",
                today > 0 ? "text-red-400" : "text-green-400",
              )}
            >
              {today > 0 ? "持续流入 · 外资看好" : today < 0 ? "持续流出 · 外资谨慎" : "无显著方向"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：龙虎榜机构席位详情
// ============================================================
function LhbDetailCard({
  entries,
  onSelectStock,
}: {
  entries: LhbEntry[];
  onSelectStock: (code: string, name: string) => void;
}) {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <DollarSign className="w-4 h-4 text-amber-400" />
        <span className="text-sm font-bold text-slate-200">龙虎榜 · 机构席位透视</span>
        <span className="text-[10px] text-slate-600 ml-auto">{entries.length} 只</span>
      </div>
      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#0d1220] text-slate-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium">名称</th>
              <th className="text-right px-3 py-2 font-medium">席位</th>
              <th className="text-right px-3 py-2 font-medium">机构买入</th>
              <th className="text-right px-3 py-2 font-medium">净买入</th>
              <th className="text-right px-4 py-2 font-medium">占成交比</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#151d2e]">
            {entries.map((e) => (
              <tr key={e.code} className="hover:bg-[#0d1220] transition-colors">
                <td className="px-4 py-2.5">
                  <button
                    onClick={() => onSelectStock(e.code, e.name)}
                    className="text-cyan-400 hover:underline text-left cursor-pointer"
                  >
                    {e.name}
                  </button>
                  <span className="text-slate-600 ml-1 text-[9px]">
                    {e.code.replace(/^(sh|sz|bj)/, "").toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right text-slate-400">{e.instSeats}席</td>
                <td className="px-3 py-2.5 text-right text-slate-300">{e.instBuyAmt}</td>
                <td
                  className={cn(
                    "px-3 py-2.5 text-right font-medium",
                    (e.netBuyAmt || "").startsWith("-") ? "text-green-400" : "text-red-400",
                  )}
                >
                  {e.netBuyAmt}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-400">{e.netRatio}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：资金流向详情
// ============================================================
function CapitalFlowDetail({
  flow,
}: {
  flow: InstitutionAggregate["capitalFlow"];
}) {
  const items = [
    { label: "主力净流入", value: flow.mainNetFlow },
    { label: "超大单净流入", value: flow.jumboNetFlow },
    { label: "中单净流入", value: flow.midNetFlow },
    { label: "小单净流入", value: flow.smallNetFlow },
  ];

  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <BarChart3 className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-bold text-slate-200">主力资金结构</span>
        <span className="text-[10px] text-slate-600 ml-auto">{flow.date || "今日"}</span>
      </div>
      <div className="p-4 space-y-3">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between">
            <span className="text-xs text-slate-400">{item.label}</span>
            <div className="flex items-center gap-2">
              <div className="w-24 h-1.5 bg-[#0d1220] rounded overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded",
                    item.value > 0 ? "bg-red-500/70" : "bg-green-500/70",
                  )}
                  style={{
                    width: `${Math.min(100, Math.abs(item.value) / 1e10 * 100)}%`,
                  }}
                />
              </div>
              <span
                className={cn(
                  "text-sm font-mono font-bold w-20 text-right",
                  item.value > 0 ? "text-red-400" : "text-green-400",
                )}
              >
                {formatFlow(item.value)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 子组件：机构持仓特征
// ============================================================
function InstitutionPositionsCard({
  positions,
}: {
  positions: InstitutionAggregate["institutionPositions"];
}) {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Shield className="w-4 h-4 text-purple-400" />
        <span className="text-sm font-bold text-slate-200">机构持仓特征</span>
      </div>
      <div className="p-4 space-y-4">
        {/* 重仓行业 */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Flame className="w-3 h-3 text-red-400" />
            <span className="text-[11px] text-slate-400">热门板块 (机构重仓)</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(positions.hotSectors || []).map((s) => (
              <span
                key={s.name}
                className="px-2.5 py-1 bg-red-500/10 border border-red-500/20 rounded text-[11px] text-red-300"
              >
                {s.name} {formatPct(s.chg5d)}
              </span>
            ))}
          </div>
        </div>

        {/* 冷门板块 */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <ArrowDown className="w-3 h-3 text-green-400" />
            <span className="text-[11px] text-slate-400">冷门板块 (资金流出)</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(positions.coldSectors || []).map((s) => (
              <span
                key={s.name}
                className="px-2.5 py-1 bg-green-500/10 border border-green-500/20 rounded text-[11px] text-green-300"
              >
                {s.name} {formatPct(s.chg5d)}
              </span>
            ))}
          </div>
        </div>

        {/* 机构净买入 TOP */}
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingUp className="w-3 h-3 text-amber-400" />
            <span className="text-[11px] text-slate-400">机构净买入 TOP</span>
          </div>
          <div className="space-y-1">
            {(positions.topInstitutionBuys || []).map((b, i) => (
              <div
                key={b.code}
                className="flex items-center justify-between px-2 py-1.5 bg-[#0d1220] rounded"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-600 font-mono w-4">{i + 1}</span>
                  <span className="text-xs text-slate-300">{b.name}</span>
                  <span className="text-[9px] text-slate-600">{b.instSeats}席</span>
                </div>
                <span className="text-xs font-mono text-amber-400">{b.netBuyAmt}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// 页面主体
// ============================================================
export default function InstitutionPage() {
  const [data, setData] = useState<InstitutionAggregate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string } | null>(null);

  const fetchData = useCallback(async () => {
    setError("");
    // 首次加载才显示 loading；刷新时保留旧数据（stale-while-revalidate）
    if (!data) setLoading(true);
    try {
      const d = await getInstitutionAggregate();
      setData(d);
    } catch (e: unknown) {
      if (!data) setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [data]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (error && !data) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-400 text-sm mb-2">加载失败: {error}</p>
        <button onClick={fetchData} className="text-xs text-cyan-400 hover:underline">
          重试
        </button>
      </div>
    );
  }

  // 骨架屏（首次加载无数据时）
  if (loading && !data) {
    return <InstitutionSkeleton />;
  }

  if (!data) return null;

  return (
    <div className="space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-fuchsia-500 to-purple-600 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">机构动向</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              龙虎榜 · 北向资金 · 主力流向 · 持仓特征 · 交易活跃度
            </p>
          </div>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#151d2e] text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
          刷新
        </button>
      </div>

      {/* 时间戳 */}
      <div className="flex items-center gap-2 text-xs text-slate-600">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        <span>数据更新: {data.timestamp} · 腾讯自选股实时行情 · 机构多维数据聚合</span>
      </div>

      {/* 第一行：活跃度 + 北向资金 + 资金结构 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ActivityGauge
          score={data.institutionActivity?.score ?? 0}
          level={data.institutionActivity?.level ?? "—"}
          lhbCount={data.institutionActivity?.lhbCount ?? 0}
          mainDirection={data.institutionActivity?.mainDirection ?? "—"}
          mainIntensity={data.institutionActivity?.mainIntensity ?? 0}
          mainFlow5d={data.institutionActivity?.mainFlow5d ?? 0}
          mainFlow20d={data.institutionActivity?.mainFlow20d ?? 0}
        />
        <NorthboundCard
          today={data.northbound?.today ?? 0}
          todayDesc={data.northbound?.todayDesc ?? "—"}
        />
        <CapitalFlowDetail flow={data.capitalFlow} />
      </div>

      {/* 第二行：龙虎榜详情 + 机构持仓特征 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <LhbDetailCard
            entries={data.lhb || []}
            onSelectStock={(code, name) => setSelectedStock({ code, name })}
          />
        </div>
        <InstitutionPositionsCard positions={data.institutionPositions} />
      </div>

      {/* 股票详情面板 */}
      {selectedStock && (
        <StockDetailPanel
          code={selectedStock.code}
          name={selectedStock.name}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </div>
  );
}

// ============================================================
// 骨架屏 — 首次加载时所见即所得
// ============================================================
function InstitutionSkeleton() {
  return (
    <div className="space-y-5 animate-slide-up">
      {/* Header 骨架 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="w-10 h-10 rounded-xl" />
          <div className="space-y-1.5">
            <Skeleton className="w-24 h-5" />
            <Skeleton className="w-48 h-3" />
          </div>
        </div>
        <Skeleton className="w-16 h-8 rounded-lg" />
      </div>

      <Skeleton className="w-64 h-3" />

      {/* 第一行：3 卡片 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SkeletonCard rows={4} />
        <SkeletonCard rows={3} />
        <SkeletonCard rows={4} />
      </div>

      {/* 第二行：龙虎榜 + 持仓 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SkeletonCard rows={6} />
        <SkeletonCard rows={5} />
      </div>
    </div>
  );
}
