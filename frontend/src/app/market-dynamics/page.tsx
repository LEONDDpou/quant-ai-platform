"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  Newspaper,
  Globe,
  ArrowUp,
  ArrowDown,
  Flame,
  DollarSign,
  Layers,
  ExternalLink,
  RefreshCw,
  Minus,
  ShieldCheck,
  ShieldAlert,
  ShieldOff,
  Clock,
  CheckCircle2,
  BarChart3,
  Radio,
  Activity,
  Thermometer,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getAShareDynamics,
  getInternationalNews,
  type AShareDynamics,
  type InternationalNews,
  type HotStock,
  type SectorRanking,
  type MarketIndexQuote,
  type StockRankings,
  type MarketNewsItem,
  type MarketBreadth,
} from "@/lib/api";
import StockDetailPanel from "@/components/stock/StockDetailPanel";
import RealtimeMarketPanel from "@/components/market/RealtimeMarketPanel";
import MarketTemperaturePanel from "@/components/market/MarketTemperaturePanel";
import {
  Skeleton,
  SkeletonCard,
  SkeletonTicker,
  SkeletonBreadth,
} from "@/components/ui/Skeleton";

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

function formatAmount(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
  return v.toFixed(0);
}

// ============================================================
// 子组件：全市场指数行情滚动条
// ============================================================
function IndexTicker({ indices }: { indices: MarketIndexQuote[] }) {
  if (!indices || indices.length === 0) return null;
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#151d2e]">
        <BarChart3 className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-bold text-slate-200">全市场指数</span>
        <span className="text-[10px] text-slate-600 ml-auto">实时行情</span>
      </div>
      <div className="flex overflow-x-auto gap-0 divide-x divide-[#151d2e]">
        {indices.map((idx) => (
          <div
            key={idx.code}
            className="flex-shrink-0 px-4 py-3 min-w-[130px] hover:bg-[#0d1220] transition-colors"
          >
            <div className="text-[10px] text-slate-500 mb-1">{idx.name}</div>
            <div className="text-sm font-mono font-bold text-slate-200">
              {idx.price > 0 ? idx.price.toFixed(2) : "—"}
            </div>
            <div
              className={cn(
                "text-xs font-mono mt-0.5",
                idx.changePct > 0
                  ? "text-red-400"
                  : idx.changePct < 0
                    ? "text-green-400"
                    : "text-slate-500",
              )}
            >
              {idx.changePct > 0 ? "+" : ""}
              {idx.changePct.toFixed(2)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 子组件：个股涨跌排行
// ============================================================
function StockRankingsCard({
  rankings,
  onSelectStock,
}: {
  rankings: StockRankings;
  onSelectStock: (code: string, name: string) => void;
}) {
  const tabs = [
    { key: "topGainers", label: "涨幅榜", icon: <ArrowUp className="w-3 h-3 text-red-400" /> },
    { key: "topLosers", label: "跌幅榜", icon: <ArrowDown className="w-3 h-3 text-green-400" /> },
  ] as const;
  const [activeTab, setActiveTab] = useState<"topGainers" | "topLosers">("topGainers");
  const data = rankings[activeTab] || [];

  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Activity className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-bold text-slate-200">个股排行</span>
      </div>
      {/* tabs */}
      <div className="flex bg-[#0d1220] border-b border-[#151d2e]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 py-2 text-xs transition-colors",
              activeTab === t.key
                ? "text-slate-200 border-b-2 border-cyan-400 bg-[#0a0e1a]/50"
                : "text-slate-500 hover:text-slate-300",
            )}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>
      <div className="max-h-[380px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#0d1220] text-slate-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium w-8">#</th>
              <th className="text-left px-2 py-2 font-medium">名称</th>
              <th className="text-right px-3 py-2 font-medium">现价</th>
              <th className="text-right px-3 py-2 font-medium">涨跌幅</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#151d2e]">
            {data.map((s, i) => (
              <tr key={s.code} className="hover:bg-[#0d1220] transition-colors">
                <td className="px-4 py-2 text-slate-600 font-mono">{i + 1}</td>
                <td className="px-2 py-2">
                  <button
                    onClick={() => onSelectStock(s.code, s.name)}
                    className="text-cyan-400 hover:underline text-left cursor-pointer"
                  >
                    {s.name}
                  </button>
                  <span className="text-slate-600 ml-1 text-[9px]">
                    {s.code.replace(/^(sh|sz|bj)/, "").toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-slate-300 font-mono">
                  {s.price.toFixed(2)}
                </td>
                <td
                  className={cn(
                    "px-3 py-2 text-right font-mono font-medium",
                    s.changePct > 0
                      ? "text-red-400"
                      : s.changePct < 0
                        ? "text-green-400"
                        : "text-slate-500",
                  )}
                >
                  {formatPct(s.changePct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：热门个股
// ============================================================
function HotStocksCard({
  stocks,
  onSelectStock,
}: {
  stocks: HotStock[];
  onSelectStock: (code: string, name: string) => void;
}) {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Flame className="w-4 h-4 text-orange-400" />
        <span className="text-sm font-bold text-slate-200">热门个股</span>
        <span className="text-[10px] text-slate-600 ml-auto">基于搜索热度</span>
      </div>
      <div className="max-h-[380px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#0d1220] text-slate-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium">名称</th>
              <th className="text-right px-4 py-2 font-medium">现价</th>
              <th className="text-right px-4 py-2 font-medium">涨跌幅</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#151d2e]">
            {stocks.map((s) => (
              <tr key={s.code} className="hover:bg-[#0d1220] transition-colors">
                <td className="px-4 py-2">
                  <button
                    onClick={() => onSelectStock(s.code, s.name)}
                    className="text-cyan-400 hover:underline text-left cursor-pointer"
                  >
                    {s.name}
                  </button>
                  <span className="text-slate-600 ml-1.5 text-[10px]">
                    {s.code.replace(/^(sh|sz|bj)/, "").toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-2 text-right text-slate-300 font-mono">
                  {s.price.toFixed(2)}
                </td>
                <td
                  className={cn(
                    "px-4 py-2 text-right font-mono font-medium",
                    s.changePct > 0 ? "text-red-400" : s.changePct < 0 ? "text-green-400" : "text-slate-500",
                  )}
                >
                  {formatPct(s.changePct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：龙虎榜（修复：key = e.code，去重已在后端保证）
// ============================================================
function LhbCard({
  entries,
  onSelectStock,
}: {
  entries: AShareDynamics["lhb"];
  onSelectStock: (code: string, name: string) => void;
}) {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <DollarSign className="w-4 h-4 text-amber-400" />
        <span className="text-sm font-bold text-slate-200">龙虎榜 · 机构席位</span>
      </div>
      <div className="max-h-[380px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-[#0d1220] text-slate-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium">名称</th>
              <th className="text-right px-3 py-2 font-medium">机构买入</th>
              <th className="text-right px-3 py-2 font-medium">净买入</th>
              <th className="text-right px-3 py-2 font-medium">占成交比</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#151d2e]">
            {entries.map((e) => (
              <tr key={e.code} className="hover:bg-[#0d1220] transition-colors">
                <td className="px-4 py-2">
                  <button
                    onClick={() => onSelectStock(e.code, e.name)}
                    className="text-cyan-400 hover:underline text-left cursor-pointer"
                  >
                    {e.name}
                  </button>
                </td>
                <td className="px-3 py-2 text-right text-slate-300">{e.instBuyAmt}</td>
                <td
                  className={cn(
                    "px-3 py-2 text-right font-medium",
                    e.netBuyAmt.startsWith("-") ? "text-green-400" : "text-red-400",
                  )}
                >
                  {e.netBuyAmt}
                </td>
                <td className="px-3 py-2 text-right text-slate-400">{e.netRatio}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：板块涨跌 + 全览表
// ============================================================
function SectorPanel({ sectors }: { sectors: SectorRanking[] }) {
  const sorted = [...sectors].sort((a, b) => b.chg5d - a.chg5d);
  const top5 = sorted.slice(0, 5);
  const bottom5 = sorted.slice(-5).reverse();

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      {/* 领涨/领跌小卡片 */}
      <div className="lg:col-span-2 grid grid-cols-1 gap-4">
        <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
          <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-[#151d2e]">
            <ArrowUp className="w-3 h-3 text-red-400" />
            <span className="text-[11px] text-slate-400 font-medium">领涨板块 (5日)</span>
          </div>
          <div className="space-y-0.5 p-2">
            {top5.map((s) => (
              <div key={s.code} className="flex items-center justify-between px-3 py-1.5 rounded bg-[#0d1220]">
                <span className="text-xs text-slate-300">{s.name}</span>
                <span className="text-xs font-mono font-medium text-red-400">{formatPct(s.chg5d)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
          <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-[#151d2e]">
            <ArrowDown className="w-3 h-3 text-green-400" />
            <span className="text-[11px] text-slate-400 font-medium">领跌板块 (5日)</span>
          </div>
          <div className="space-y-0.5 p-2">
            {bottom5.map((s) => (
              <div key={s.code} className="flex items-center justify-between px-3 py-1.5 rounded bg-[#0d1220]">
                <span className="text-xs text-slate-300">{s.name}</span>
                <span className="text-xs font-mono font-medium text-green-400">{formatPct(s.chg5d)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 全览表 */}
      <div className="lg:col-span-3 bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
          <Layers className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-bold text-slate-200">申万一级行业 · 全览 (31 个)</span>
        </div>
        <div className="max-h-[420px] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-[#0d1220] text-slate-500">
              <tr>
                <th className="text-left px-4 py-2 font-medium">板块</th>
                <th className="text-right px-3 py-2 font-medium">5日</th>
                <th className="text-right px-3 py-2 font-medium">20日</th>
                <th className="text-right px-3 py-2 font-medium">60日</th>
                <th className="text-right px-3 py-2 font-medium">250日</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#151d2e]">
              {sectors.map((s) => (
                <tr key={s.code} className="hover:bg-[#0d1220] transition-colors">
                  <td className="px-4 py-2 text-slate-300">{s.name}</td>
                  <ChgCell v={s.chg5d} />
                  <ChgCell v={s.chg20d} />
                  <ChgCell v={s.chg60d} />
                  <ChgCell v={s.chg250d} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：资金流向
// ============================================================
function CapitalFlowCard({ flow }: { flow: AShareDynamics["capitalFlow"] }) {
  const items = [
    { label: "主力净流入", value: flow.mainNetFlow },
    { label: "超大单", value: flow.jumboNetFlow },
    { label: "中单", value: flow.midNetFlow },
    { label: "小单", value: flow.smallNetFlow },
  ];

  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <TrendingUp className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-bold text-slate-200">主力资金流向</span>
        <span className="text-[10px] text-slate-600 ml-auto">{flow.date || "今日"}</span>
      </div>
      <div className="p-4 space-y-3">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between">
            <span className="text-xs text-slate-400">{item.label}</span>
            <span
              className={cn(
                "text-sm font-mono font-bold",
                item.value > 0 ? "text-red-400" : "text-green-400",
              )}
            >
              {item.value > 0 ? "+" : ""}
              {formatFlow(item.value)}
            </span>
          </div>
        ))}
        <div className="pt-3 mt-3 border-t border-[#151d2e] grid grid-cols-2 gap-3">
          <div>
            <div className="text-[10px] text-slate-600 mb-0.5">5日主力</div>
            <div
              className={cn("text-xs font-mono font-medium", flow.mainNetFlow5d > 0 ? "text-red-400" : "text-green-400")}
            >
              {formatFlow(flow.mainNetFlow5d)}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-slate-600 mb-0.5">20日主力</div>
            <div
              className={cn("text-xs font-mono font-medium", flow.mainNetFlow20d > 0 ? "text-red-400" : "text-green-400")}
            >
              {formatFlow(flow.mainNetFlow20d)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// 子组件：实时公告资讯
// ============================================================
function MarketNewsCard({ news }: { news: MarketNewsItem[] }) {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Radio className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-bold text-slate-200">实时公告资讯</span>
        <span className="text-[10px] text-slate-600 ml-auto">{news.length} 条</span>
      </div>
      <div className="max-h-[420px] overflow-y-auto divide-y divide-[#151d2e]">
        {news.map((n, i) => (
          <div key={`${n.time}-${i}`} className="px-4 py-2.5 hover:bg-[#0d1220] transition-colors">
            <div className="flex items-start gap-2">
              <span className="text-[10px] text-slate-600 mt-0.5 min-w-[44px]">{n.time?.slice(-8) || ""}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-200 leading-relaxed line-clamp-2">{n.title}</p>
                {n.summary && (
                  <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{n.summary}</p>
                )}
              </div>
              <span className="text-[9px] text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded flex-shrink-0">
                {n.source || n.type}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 子组件：市场宽度 / 涨跌统计（v1.3.1 新增）
// ============================================================
function MarketBreadthCard({ breadth }: { breadth: MarketBreadth }) {
  const agg = breadth.aggregate;
  if (!agg || agg.total === 0) return null;

  const upRatio = agg.total > 0 ? (agg.upCount / agg.total * 100) : 50;
  const downRatio = agg.total > 0 ? (agg.downCount / agg.total * 100) : 50;
  const flatRatio = agg.total > 0 ? (agg.flatCount / agg.total * 100) : 0;

  // 市场宽度评级
  let breadthLabel: string;
  let breadthColor: string;
  if (agg.breadthPct >= 70) { breadthLabel = "强势普涨"; breadthColor = "text-red-400"; }
  else if (agg.breadthPct >= 55) { breadthLabel = "偏强"; breadthColor = "text-amber-400"; }
  else if (agg.breadthPct >= 45) { breadthLabel = "均衡"; breadthColor = "text-slate-400"; }
  else if (agg.breadthPct >= 30) { breadthLabel = "偏弱"; breadthColor = "text-cyan-400"; }
  else { breadthLabel = "弱势普跌"; breadthColor = "text-green-400"; }

  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Layers className="w-4 h-4 text-purple-400" />
        <span className="text-sm font-bold text-slate-200">市场宽度 · 涨跌统计</span>
        <span className={cn("badge text-[10px] ml-auto font-medium", breadthColor.replace("text-", "bg-").replace("400", "500/15 ") + breadthColor)}>
          {breadthLabel}
        </span>
      </div>
      <div className="p-4">
        {/* 核心 KPI 三栏 */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-red-500/5 border border-red-500/15 rounded-lg p-3 text-center">
            <div className="text-[10px] text-slate-500 mb-1">上涨</div>
            <div className="text-xl font-bold font-mono text-red-400">{agg.upCount}</div>
            <div className="text-[10px] text-slate-600">{upRatio.toFixed(1)}%</div>
          </div>
          <div className="bg-[#0d1220] border border-[#151d2e] rounded-lg p-3 text-center">
            <div className="text-[10px] text-slate-500 mb-1">平盘</div>
            <div className="text-xl font-bold font-mono text-slate-400">{agg.flatCount}</div>
            <div className="text-[10px] text-slate-600">{flatRatio.toFixed(1)}%</div>
          </div>
          <div className="bg-green-500/5 border border-green-500/15 rounded-lg p-3 text-center">
            <div className="text-[10px] text-slate-500 mb-1">下跌</div>
            <div className="text-xl font-bold font-mono text-green-400">{agg.downCount}</div>
            <div className="text-[10px] text-slate-600">{downRatio.toFixed(1)}%</div>
          </div>
        </div>

        {/* 涨跌比进度条 */}
        <div className="h-2.5 bg-[#0d1220] rounded-full overflow-hidden flex">
          {agg.upCount > 0 && (
            <div
              className="h-full bg-gradient-to-r from-red-600 to-red-400"
              style={{ width: `${upRatio}%`, minWidth: upRatio > 0 ? "2px" : "0" }}
            />
          )}
          {agg.flatCount > 0 && (
            <div
              className="h-full bg-slate-600"
              style={{ width: `${flatRatio}%`, minWidth: flatRatio > 0 ? "2px" : "0" }}
            />
          )}
          {agg.downCount > 0 && (
            <div
              className="h-full bg-gradient-to-r from-green-400 to-green-600"
              style={{ width: `${downRatio}%`, minWidth: downRatio > 0 ? "2px" : "0" }}
            />
          )}
        </div>

        {/* 涨跌停 */}
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="flex items-center justify-between bg-[#0d1220] rounded-lg p-2.5">
            <div className="flex items-center gap-1.5">
              <ArrowUp className="w-3.5 h-3.5 text-red-400" />
              <span className="text-[11px] text-slate-400">涨停 / 接近涨停</span>
            </div>
            <span className="text-sm font-bold font-mono text-red-400">{agg.limitUp} 家</span>
          </div>
          <div className="flex items-center justify-between bg-[#0d1220] rounded-lg p-2.5">
            <div className="flex items-center gap-1.5">
              <ArrowDown className="w-3.5 h-3.5 text-green-400" />
              <span className="text-[11px] text-slate-400">跌停 / 接近跌停</span>
            </div>
            <span className="text-sm font-bold font-mono text-green-400">{agg.limitDown} 家</span>
          </div>
        </div>

        {/* 沪深分市场明细 */}
        {(breadth.shanghai || breadth.shenzhen) && (
          <div className="grid grid-cols-2 gap-3 mt-4 pt-4 border-t border-[#151d2e]">
            {breadth.shanghai && (
              <div>
                <div className="text-[10px] text-slate-600 mb-1">沪市</div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-red-400">↑{breadth.shanghai.upCount}</span>
                  <span className="font-mono text-green-400">↓{breadth.shanghai.downCount}</span>
                  <span className="font-mono text-slate-500">—{breadth.shanghai.flatCount}</span>
                </div>
              </div>
            )}
            {breadth.shenzhen && (
              <div>
                <div className="text-[10px] text-slate-600 mb-1">深市</div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-red-400">↑{breadth.shenzhen.upCount}</span>
                  <span className="font-mono text-green-400">↓{breadth.shenzhen.downCount}</span>
                  <span className="font-mono text-slate-500">—{breadth.shenzhen.flatCount}</span>
                </div>
              </div>
            )}
          </div>
        )}

        <p className="text-[9px] text-slate-700 mt-3">
          沪深两市合计 {agg.total} 只 · 数据更新时间 {breadth.timestamp}
        </p>
      </div>
    </div>
  );
}

// ============================================================
// 页面主体
// ============================================================
export default function MarketDynamicsPage() {
  const [tab, setTab] = useState<"a-share" | "intl" | "temperature">("a-share");

  // A 股动态
  const [aDynamics, setADynamics] = useState<AShareDynamics | null>(null);
  const [aLoading, setALoading] = useState(true);
  const [aError, setAError] = useState("");
  const [aCountdown, setACountdown] = useState(30);
  const aCountdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const aRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 国际新闻
  const [intlNews, setIntlNews] = useState<InternationalNews | null>(null);
  const [intlLoading, setIntlLoading] = useState(false);
  const [intlError, setIntlError] = useState("");
  const [intlCountdown, setIntlCountdown] = useState(120);
  const intlCountdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const intlRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 股票详情面板
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string } | null>(null);

  const fetchADynamics = useCallback(async () => {
    setAError("");
    // 首次加载显示 loading；后续刷新保留旧数据
    if (!aDynamics) setALoading(true);
    try {
      const data = await getAShareDynamics();
      setADynamics(data);
      setACountdown(30);
    } catch (e: unknown) {
      if (!aDynamics) setAError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setALoading(false);
    }
  }, [aDynamics]);

  const fetchIntlNews = useCallback(async (forceRefresh = false) => {
    setIntlLoading(true);
    setIntlError("");
    try {
      const data = await getInternationalNews(forceRefresh);
      setIntlNews(data);
      setIntlCountdown(120);
    } catch (e: unknown) {
      setIntlError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setIntlLoading(false);
    }
  }, []);

  // A 股首次加载
  useEffect(() => {
    fetchADynamics();
  }, [fetchADynamics]);

  // 切换到国际新闻 tab 时首次加载
  useEffect(() => {
    if (tab === "intl" && !intlNews && !intlLoading) {
      fetchIntlNews();
    }
  }, [tab, intlNews, intlLoading, fetchIntlNews]);

  // A 股自动刷新（30s） — v1.3 新增
  useEffect(() => {
    if (tab !== "a-share") {
      if (aCountdownRef.current) clearInterval(aCountdownRef.current);
      if (aRefreshRef.current) clearInterval(aRefreshRef.current);
      return;
    }
    aCountdownRef.current = setInterval(() => {
      setACountdown((prev) => (prev <= 1 ? 30 : prev - 1));
    }, 1000);
    aRefreshRef.current = setInterval(() => {
      fetchADynamics();
    }, 30_000);
    return () => {
      if (aCountdownRef.current) clearInterval(aCountdownRef.current);
      if (aRefreshRef.current) clearInterval(aRefreshRef.current);
    };
  }, [tab, fetchADynamics]);

  // 国际新闻自动刷新（120s）
  useEffect(() => {
    if (tab !== "intl") {
      if (intlCountdownRef.current) clearInterval(intlCountdownRef.current);
      if (intlRefreshRef.current) clearInterval(intlRefreshRef.current);
      return;
    }
    intlCountdownRef.current = setInterval(() => {
      setIntlCountdown((prev) => (prev <= 1 ? 120 : prev - 1));
    }, 1000);
    intlRefreshRef.current = setInterval(() => {
      fetchIntlNews(true);
    }, 120_000);
    return () => {
      if (intlCountdownRef.current) clearInterval(intlCountdownRef.current);
      if (intlRefreshRef.current) clearInterval(intlRefreshRef.current);
    };
  }, [tab, fetchIntlNews]);

  const formatCountdown = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-200">
      {/* 顶栏 */}
      <div className="sticky top-0 z-20 bg-[#070b14]/95 backdrop-blur border-b border-[#151d2e]">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-slate-100">市场动态</h1>
            <div className="flex bg-[#0a0e1a] border border-[#151d2e] rounded-lg p-0.5">
              <button
                onClick={() => setTab("a-share")}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  tab === "a-share" ? "bg-cyan-500/20 text-cyan-400" : "text-slate-500 hover:text-slate-300",
                )}
              >
                <Flame className="w-3 h-3 inline mr-1" />A 股实时动态
              </button>
              <button
                onClick={() => setTab("intl")}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  tab === "intl" ? "bg-purple-500/20 text-purple-400" : "text-slate-500 hover:text-slate-300",
                )}
              >
                <Globe className="w-3 h-3 inline mr-1" />国际新闻
              </button>
              <button
                onClick={() => setTab("temperature")}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  tab === "temperature" ? "bg-orange-500/20 text-orange-400" : "text-slate-500 hover:text-slate-300",
                )}
              >
                <Thermometer className="w-3 h-3 inline mr-1" />市场温度
              </button>
            </div>
          </div>
          {(tab === "a-share" || tab === "intl") && (
            <button
              onClick={() => (tab === "a-share" ? fetchADynamics() : fetchIntlNews(true))}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#151d2e] text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              <RefreshCw className={cn("w-3 h-3", (aLoading || intlLoading) && "animate-spin")} />
              刷新
              <span className="text-[10px] text-slate-600 ml-0.5 tabular-nums">
                {tab === "a-share" ? formatCountdown(aCountdown) : formatCountdown(intlCountdown)}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* 内容区 */}
      <div className="p-6">
        {/* ======== Tab 1: A 股实时动态 ======== */}
        {tab === "a-share" && (
          <>
            {aLoading && !aDynamics && <ASkeletonDynamics />}

            {aError && !aDynamics && (
              <div className="p-8 text-center">
                <p className="text-red-400 text-sm mb-2">加载失败: {aError}</p>
                <button onClick={fetchADynamics} className="text-xs text-cyan-400 hover:underline">
                  重试
                </button>
              </div>
            )}

            {aDynamics && (
              <div className="space-y-5">
                {/* 时间戳 + 刷新状态 */}
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <div className={cn("w-1.5 h-1.5 rounded-full", aLoading ? "bg-amber-400 animate-pulse" : "bg-emerald-400")} />
                  <span>数据更新: {aDynamics.timestamp} · 腾讯自选股（每 30 秒轮询刷新）· 下次刷新: {formatCountdown(aCountdown)}</span>
                </div>

                {/* 数据源缺失提示：接口返回空数据时显式告知，避免"静默空屏"误导 */}
                {aDynamics && (aDynamics.marketIndices?.length ?? 0) === 0 &&
                  (aDynamics.stockRankings?.topGainers?.length ?? 0) === 0 &&
                  (aDynamics.hotStocks?.length ?? 0) === 0 && (
                  <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
                    数据源（腾讯自选股）暂不可用，当前无行情数据。请稍后重试或检查网络。
                  </div>
                )}

                {/* 全市场指数行情滚动条 */}
                <IndexTicker indices={aDynamics.marketIndices} />

                {/* 市场宽度 · 涨跌统计（v1.3.1 新增） */}
                <MarketBreadthCard breadth={aDynamics.marketBreadth} />

                {/* 第一行：个股排行 + 热门个股 + 龙虎榜 */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <StockRankingsCard
                    rankings={aDynamics.stockRankings}
                    onSelectStock={(code, name) => setSelectedStock({ code, name })}
                  />
                  <HotStocksCard
                    stocks={aDynamics.hotStocks}
                    onSelectStock={(code, name) => setSelectedStock({ code, name })}
                  />
                  <LhbCard
                    entries={aDynamics.lhb}
                    onSelectStock={(code, name) => setSelectedStock({ code, name })}
                  />
                </div>

                {/* 第二行：板块全览 + 资金流向 */}
                <SectorPanel sectors={aDynamics.sectorRankings} />

                {/* 第三行：资金流向详情 + 公告资讯 */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <CapitalFlowCard flow={aDynamics.capitalFlow} />
                  <MarketNewsCard news={aDynamics.marketNews} />
                </div>

                {/* 实时行情模块（迁移自原独立实时行情模块，已去重：涨跌排行榜 / 市场宽度 与上方重复，已移除） */}
                <div className="flex items-center gap-2 pt-3 mt-3 border-t border-[#151d2e]">
                  <Radio className="w-4 h-4 text-cyan-400" />
                  <h2 className="text-sm font-bold text-slate-200">实时行情模块</h2>
                  <span className="text-[10px] text-slate-600">WebSocket 实时推送 · 点击行情表行查看 K 线 / 个股资金流</span>
                </div>
                <RealtimeMarketPanel embedded />
              </div>
            )}
          </>
        )}

        {/* ======== Tab 2: 国际新闻 ======== */}
        {tab === "intl" && (
          <>
            {intlLoading && !intlNews && (
              <div className="flex items-center justify-center py-20">
                <RefreshCw className="w-6 h-6 animate-spin text-purple-400" />
              </div>
            )}

            {intlError && !intlNews && (
              <div className="p-8 text-center">
                <p className="text-red-400 text-sm mb-2">加载失败: {intlError}</p>
                <button onClick={() => fetchIntlNews(true)} className="text-xs text-purple-400 hover:underline">
                  重试
                </button>
              </div>
            )}

            {intlNews && (
              <div className="space-y-6">
                {/* 时间戳 + 来源 + 刷新状态 */}
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-xs text-slate-600">
                      <div className={cn("w-1.5 h-1.5 rounded-full", intlLoading ? "bg-amber-400 animate-pulse" : "bg-emerald-400")} />
                      <span>更新: {intlNews.timestamp}</span>
                    </div>
                    {intlLoading && (
                      <span className="text-[10px] text-amber-400/70 animate-pulse">刷新中...</span>
                    )}
                    <span className="text-[10px] text-slate-600">下次刷新: {formatCountdown(intlCountdown)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {intlNews.sources.map((src) => (
                      <span key={src} className="px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 rounded text-[10px] text-purple-400">
                        {src}
                      </span>
                    ))}
                  </div>
                </div>

                {/* 可信度概览 */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-emerald-500/5 border border-emerald-500/15 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 mb-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-[10px] text-emerald-400 font-medium">高可信</span>
                    </div>
                    <div className="text-lg font-bold text-emerald-300">{intlNews.highCredibilityCount ?? 0}</div>
                  </div>
                  <div className="bg-amber-500/5 border border-amber-500/15 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 mb-1">
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                      <span className="text-[10px] text-amber-400 font-medium">中等可信</span>
                    </div>
                    <div className="text-lg font-bold text-amber-300">{(intlNews.verifiedCount ?? 0) - (intlNews.highCredibilityCount ?? 0)}</div>
                  </div>
                  <div className="bg-red-500/5 border border-red-500/15 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 mb-1">
                      <ShieldOff className="w-3.5 h-3.5 text-red-400" />
                      <span className="text-[10px] text-red-400 font-medium">待审核</span>
                    </div>
                    <div className="text-lg font-bold text-red-300">{intlNews.headlines.length - (intlNews.verifiedCount ?? 0)}</div>
                  </div>
                </div>

                {/* AI 摘要 */}
                {intlNews.summaryText && (
                  <div className="bg-[#0a0e1a] border border-purple-500/20 rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Globe className="w-4 h-4 text-purple-400" />
                      <span className="text-sm font-bold text-purple-300">AI 市场简讯摘要</span>
                      <span className="text-[10px] text-slate-600 ml-auto">DeepSeek 生成</span>
                    </div>
                    <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{intlNews.summaryText}</div>
                  </div>
                )}

                {/* 新闻列表 */}
                <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
                    <Newspaper className="w-4 h-4 text-cyan-400" />
                    <span className="text-sm font-bold text-slate-200">新闻列表 ({intlNews.headlines.length} 条)</span>
                    <span className="text-[10px] text-slate-600 ml-auto">AI 翻译 + 真实性审核</span>
                  </div>
                  <div className="divide-y divide-[#151d2e] max-h-[700px] overflow-y-auto">
                    {intlNews.headlines.map((h, i) => (
                      <div key={h.id || i} className="px-4 py-3 hover:bg-[#0d1220] transition-colors">
                        <div className="flex items-start gap-3">
                          <span className="text-[10px] text-slate-600 mt-0.5 min-w-[18px]">{i + 1}</span>
                          <div className="flex-1 min-w-0 space-y-1">
                            <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-sm text-slate-200 hover:text-cyan-400 transition-colors line-clamp-2 font-medium">
                              {h.titleZh || h.title}
                            </a>
                            {h.titleZh && h.titleZh !== h.title && (
                              <p className="text-[10px] text-slate-600 line-clamp-1">EN: {h.title}</p>
                            )}
                            {h.verificationNote && (
                              <p className="text-[10px] text-slate-500">
                                <CheckCircle2 className="w-2.5 h-2.5 inline mr-0.5 text-slate-600" />
                                {h.verificationNote}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-col items-end gap-1 flex-shrink-0">
                            <span className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">{h.source}</span>
                            {h.published && (
                              <span className="flex items-center gap-1 text-[10px] text-slate-600">
                                <Clock className="w-2.5 h-2.5" />{h.published}
                              </span>
                            )}
                            {h.credibility && (
                              <span className={cn(
                                "flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded font-medium",
                                h.credibility === "high" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                                h.credibility === "medium" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" :
                                "bg-red-500/10 text-red-400 border border-red-500/20",
                              )}>
                                {h.credibility === "high" ? <ShieldCheck className="w-2.5 h-2.5" /> : h.credibility === "medium" ? <ShieldAlert className="w-2.5 h-2.5" /> : <ShieldOff className="w-2.5 h-2.5" />}
                                {h.credibility === "high" ? "高可信" : h.credibility === "medium" ? "中等" : "低可信"}
                              </span>
                            )}
                            <ExternalLink className="w-3 h-3 text-slate-700" />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* ======== Tab 3: 市场温度（合并自市场温度模块） ======== */}
        {tab === "temperature" && <MarketTemperaturePanel />}
      </div>

      {/* 股票详情面板 */}
      {selectedStock && (
        <StockDetailPanel code={selectedStock.code} name={selectedStock.name} onClose={() => setSelectedStock(null)} />
      )}
    </div>
  );
}

// 辅助：涨跌幅单元格
function ChgCell({ v }: { v: number }) {
  return (
    <td className={cn("px-3 py-2 text-right font-mono text-xs", v > 0 ? "text-red-400" : v < 0 ? "text-green-400" : "text-slate-500")}>
      {v > 0 ? "+" : ""}{v.toFixed(2)}%
    </td>
  );
}

// ============================================================
// 骨架屏：A 股动态首次加载
// ============================================================
function ASkeletonDynamics() {
  return (
    <div className="space-y-5">
      <Skeleton className="w-64 h-3" />
      <SkeletonTicker />
      <SkeletonBreadth />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SkeletonCard rows={4} />
        <SkeletonCard rows={4} />
        <SkeletonCard rows={4} />
      </div>
      <SkeletonCard rows={6} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SkeletonCard rows={5} />
        <SkeletonCard rows={5} />
      </div>
    </div>
  );
}
