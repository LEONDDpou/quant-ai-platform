"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchAccountOverview,
  type AccountOverview,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  BarChart3,
  DollarSign,
  PiggyBank,
  TrendingUp,
} from "lucide-react";

export default function AccountOverviewPanel({
  onSelectAccount,
}: {
  onSelectAccount?: (id: number) => void;
}) {
  const [overview, setOverview] = useState<AccountOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const ov = await fetchAccountOverview("demo");
      setOverview(ov);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !overview) {
    return (
      <div className="card p-5">
        <div className="flex justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-2 border-blue-400 border-t-transparent" />
        </div>
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="card p-5">
        <div className="text-gray-400 text-xs py-4 text-center">
          {error || "暂无数据"}
        </div>
      </div>
    );
  }

  return (
    <div className="card p-5 space-y-4">
      <h2 className="section-title flex items-center gap-2">
        <BarChart3 className="w-5 h-5" /> 账户总览
      </h2>

      {error && <div className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded">{error}</div>}

      {/* KPI 卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-lg border p-3 bg-gradient-to-br from-blue-50 to-white">
          <div className="flex items-center gap-1 text-[10px] text-gray-500">
            <PiggyBank className="w-3 h-3" /> 总资产
          </div>
          <div className="text-lg font-bold text-gray-800 mt-1">
            {(overview.totalAssets / 10000).toFixed(1)}万
          </div>
        </div>
        <div className="rounded-lg border p-3 bg-gradient-to-br from-green-50 to-white">
          <div className="flex items-center gap-1 text-[10px] text-gray-500">
            <TrendingUp className="w-3 h-3" /> 总收益
          </div>
          <div className={cn(
            "text-lg font-bold mt-1",
            overview.totalPnl >= 0 ? "text-green-600" : "text-red-600",
          )}>
            {overview.totalPnlPct.toFixed(1)}%
          </div>
        </div>
        <div className="rounded-lg border p-3 bg-gradient-to-br from-purple-50 to-white">
          <div className="flex items-center gap-1 text-[10px] text-gray-500">
            <DollarSign className="w-3 h-3" /> 账户数
          </div>
          <div className="text-lg font-bold text-gray-800 mt-1">
            {overview.totalAccounts}
            <span className="text-xs text-gray-400 ml-1">
              ({overview.activeCount} 活跃)
            </span>
          </div>
        </div>
        <div className="rounded-lg border p-3 bg-gradient-to-br from-orange-50 to-white">
          <div className="flex items-center gap-1 text-[10px] text-gray-500">
            持仓市值
          </div>
          <div className="text-lg font-bold text-gray-800 mt-1">
            {(overview.totalPositionValue / 10000).toFixed(1)}万
          </div>
        </div>
      </div>

      {/* 账户明细列表 */}
      <div className="space-y-1.5 max-h-60 overflow-y-auto">
        {overview.accounts.map((acc) => (
          <div
            key={acc.id}
            className="flex items-center justify-between p-2.5 rounded-lg border hover:border-blue-300 cursor-pointer transition-colors"
            onClick={() => onSelectAccount?.(acc.id)}
          >
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-600 flex-shrink-0">
                {acc.name.charAt(0)}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold truncate">{acc.name}</div>
                <div className="text-[10px] text-gray-400">
                  资产 {acc.positionRatio.toFixed(0)}% 仓位
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className={cn(
                "text-sm font-bold",
                acc.totalPnl >= 0 ? "text-green-600" : "text-red-600",
              )}>
                {acc.totalPnlPct >= 0 ? "+" : ""}{acc.totalPnlPct.toFixed(1)}%
              </div>
              <div className="text-[10px] text-gray-400">
                {(acc.totalAssets / 10000).toFixed(1)}万
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
