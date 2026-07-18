"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchLatestReview,
  fetchReviewHistory,
  generateReview,
  type PaperDailyReview,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  BookOpen,
  Calendar,
  FileText,
  RefreshCw,
  TrendingUp,
  TrendingDown,
} from "lucide-react";

export default function DailyReviewPanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [latest, setLatest] = useState<PaperDailyReview | null>(null);
  const [history, setHistory] = useState<PaperDailyReview[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (accountId == null) return;
    setLoading(true);
    setError("");
    try {
      const [lat, hist] = await Promise.all([
        fetchLatestReview(accountId).catch(() => null),
        fetchReviewHistory(accountId, 10),
      ]);
      setLatest(lat);
      setHistory(hist);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleGenerate = async () => {
    if (accountId == null) return;
    setLoading(true);
    setError("");
    try {
      const review = await generateReview(accountId);
      setLatest(review);
      setHistory((prev) => [review, ...prev]);
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "生成失败");
    } finally {
      setLoading(false);
    }
  };

  const todayPnl = latest?.pnlSummary?.todayPnl as number | undefined;
  const isPositive = todayPnl != null && todayPnl >= 0;

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="section-title flex items-center gap-2">
          <BookOpen className="w-5 h-5" /> AI 每日复盘
        </h2>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-400">
            {latest ? `最近: ${latest.date}` : "暂无复盘"}
          </span>
          <button
            className={cn(
              "btn-primary text-xs px-3 py-1 flex items-center gap-1",
              !accountId && "opacity-50 cursor-not-allowed",
            )}
            disabled={!accountId || loading}
            onClick={handleGenerate}
          >
            <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
            生成复盘
          </button>
        </div>
      </div>

      {error && <div className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded">{error}</div>}

      {/* 最新复盘 */}
      {latest ? (
        <div className="space-y-3">
          {/* 摘要横幅 */}
          <div className={cn(
            "rounded-lg p-4 border",
            isPositive
              ? "bg-gradient-to-r from-green-50 to-white border-green-200"
              : "bg-gradient-to-r from-red-50 to-white border-red-200",
          )}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isPositive ? (
                  <TrendingUp className="w-5 h-5 text-green-500" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-red-500" />
                )}
                <span className="text-sm font-semibold">{latest.summary}</span>
              </div>
              <span className={cn(
                "badge text-[10px]",
                latest.generatedBy === "llm" ? "badge-blue" : "badge-gray",
              )}>
                {latest.generatedBy === "llm" ? "LLM" : "规则"}
              </span>
            </div>
          </div>

          {/* 4 KPI */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="rounded-lg border p-3">
              <div className="text-[10px] text-gray-500">今日盈亏</div>
              <div className={cn("text-base font-bold mt-0.5",
                (latest.pnlSummary?.todayPnl as number) >= 0 ? "text-green-600" : "text-red-600",
              )}>
                {latest.pnlSummary?.todayPnl != null
                  ? `${(latest.pnlSummary.todayPnl as number).toFixed(0)} 元`
                  : "—"}
              </div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-[10px] text-gray-500">总资产</div>
              <div className="text-base font-bold mt-0.5">
                {latest.performance?.totalAssets != null
                  ? `${((latest.performance.totalAssets as number) / 10000).toFixed(1)}万`
                  : "—"}
              </div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-[10px] text-gray-500">持仓</div>
              <div className="text-base font-bold mt-0.5">
                {latest.pnlSummary?.positionCount != null
                  ? `${latest.pnlSummary.positionCount} 只`
                  : "—"}
                <span className="text-xs text-gray-400 ml-1">
                  {latest.performance?.positionRatio != null
                    ? `(${Number(latest.performance.positionRatio).toFixed(0)}%)`
                    : ""}
                </span>
              </div>
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-[10px] text-gray-500">今日成交</div>
              <div className="text-base font-bold mt-0.5">
                {latest.tradesSummary?.filledBuys != null
                  ? `${latest.tradesSummary.filledBuys}B / ${latest.tradesSummary.filledSells}S`
                  : "—"}
              </div>
            </div>
          </div>

          {/* 市场概况 */}
          {latest.marketSummary && (
            <div className="rounded-lg border p-3">
              <div className="text-xs font-semibold text-gray-600 mb-1">📈 市场概况</div>
              <div className="text-xs text-gray-600 leading-relaxed">{latest.marketSummary}</div>
            </div>
          )}

          {/* 决策回顾 */}
          {latest.decisions && latest.decisions.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-600 mb-1">📋 今日交易决策</div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {latest.decisions.slice(0, 10).map((d: unknown, i: number) => {
                  const dec = d as Record<string, unknown>;
                  return (
                    <div key={i} className="flex items-center justify-between text-xs px-3 py-1.5 bg-gray-50 rounded">
                      <span className="font-mono">{String(dec.code || "")}</span>
                      <span className={cn(
                        dec.direction === "buy" ? "text-red-500" : "text-green-500",
                      )}>
                        {String(dec.direction || "").toUpperCase()} {String(dec.shares || "0")}股
                      </span>
                      <span className="text-gray-400">
                        @{String(dec.price || "—")} {String(dec.status || "")}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="text-gray-400 text-xs py-8 text-center">
          {loading ? "加载中..." : "暂无复盘，点击「生成复盘」创建今日报告"}
        </div>
      )}

      {/* 历史列表 */}
      {history.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-gray-600 mb-1 flex items-center gap-1">
            <Calendar className="w-3 h-3" /> 历史复盘
          </div>
          <div className="space-y-1 max-h-36 overflow-y-auto">
            {history.slice(0, 10).map((r) => (
              <div
                key={r.id}
                className={cn(
                  "flex items-center justify-between text-xs px-3 py-1.5 rounded cursor-pointer",
                  latest?.id === r.id ? "bg-blue-50 border border-blue-200" : "bg-gray-50 hover:bg-gray-100",
                )}
                onClick={() => setLatest(r)}
              >
                <span className="font-medium">{r.date}</span>
                <span className="text-gray-500 truncate max-w-[200px]">{r.summary}</span>
                <span className="text-[10px] text-gray-400">{r.generatedBy}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
