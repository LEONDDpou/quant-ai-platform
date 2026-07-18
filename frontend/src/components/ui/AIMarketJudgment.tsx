"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/config";
import {
  TrendingUp,
  Target,
  Shield,
  Zap,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";

interface MarketJudgment {
  marketTrend: string;
  marketSummary: string;
  positionAdvice: string;
  riskStars: number;
  aiScore: number;
  temperatureScore: number;
  strongSectors: string[];
  weakSectors: string[];
  hotThemes: string[];
  recommendedStrategies: string[];
  keyRisks: string[];
  actionPlan: string;
  generatedBy: string;
  model: string;
}

export function AIMarketJudgment() {
  const [data, setData] = useState<MarketJudgment | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchJudgment = () => {
    setLoading(true);
    fetch(`${API_BASE}/api/ai-agent/market-judgment`, {
      method: "POST",
    })
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchJudgment();
  }, []);

  if (loading && !data) {
    return (
      <div className="bg-[#0d1220] border border-[#1a2235] rounded-xl p-5 animate-pulse">
        <div className="h-4 w-28 bg-[#1a2235] rounded mb-3" />
        <div className="space-y-2">
          <div className="h-3 bg-[#1a2235] rounded w-full" />
          <div className="h-3 bg-[#1a2235] rounded w-4/5" />
          <div className="h-3 bg-[#1a2235] rounded w-3/5" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-[#0d1220] border border-[#1a2235] rounded-xl p-5">
        <div className="text-slate-500 text-sm">AI 市场研判加载中...</div>
      </div>
    );
  }

  const trendColor =
    data.marketTrend.includes("强") || data.marketTrend.includes("偏强")
      ? "#22c55e"
      : data.marketTrend.includes("弱")
      ? "#ef4444"
      : "#eab308";

  return (
    <div className="bg-[#0d1220] border border-[#1a2235] rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">AI 市场研判</h3>
        <button
          onClick={fetchJudgment}
          className="text-[10px] text-cyan-500 hover:text-cyan-400 transition-colors"
          disabled={loading}
        >
          {loading ? "刷新中..." : "刷新"}
        </button>
      </div>

      {/* 大盘判断 + 风险星级 + AI评分 */}
      <div className="flex items-center gap-4">
        <div
          className="px-3 py-1.5 rounded-lg text-sm font-bold"
          style={{ backgroundColor: trendColor + "15", color: trendColor }}
        >
          {data.marketTrend}
        </div>
        <div className="flex gap-0.5">
          {Array.from({ length: 5 }, (_, i) => (
            <Zap
              key={i}
              className={`w-3.5 h-3.5 ${
                i < data.riskStars ? "text-amber-400" : "text-slate-700"
              }`}
              fill={i < data.riskStars ? "#fbbf24" : "none"}
            />
          ))}
          <span className="text-[10px] text-slate-500 ml-1">
            风险 {data.riskStars}/5
          </span>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <span className="text-[10px] text-slate-500">AI评分</span>
          <span
            className="text-sm font-bold font-mono"
            style={{ color: data.aiScore > 65 ? "#22c55e" : data.aiScore > 40 ? "#eab308" : "#ef4444" }}
          >
            {data.aiScore}
          </span>
        </div>
      </div>

      {/* 市场描述 */}
      <p className="text-xs text-slate-400 leading-relaxed">{data.marketSummary}</p>

      {/* 仓位建议 */}
      <div className="flex items-center gap-2 p-3 bg-[#0a0f1a] rounded-lg border border-[#1a2235]">
        <Target className="w-4 h-4 text-cyan-400" />
        <span className="text-xs text-slate-300 font-medium">{data.positionAdvice}</span>
      </div>

      {/* 四宫格：强势板块 / 弱势板块 / 热点题材 / 推荐策略 */}
      <div className="grid grid-cols-2 gap-2">
        <InfoCell
          icon={<TrendingUp className="w-3 h-3 text-emerald-400" />}
          title="强势板块"
          items={data.strongSectors}
          color="emerald"
        />
        <InfoCell
          icon={<AlertTriangle className="w-3 h-3 text-red-400" />}
          title="弱势板块"
          items={data.weakSectors}
          color="red"
        />
        <InfoCell
          icon={<Shield className="w-3 h-3 text-amber-400" />}
          title="热点题材"
          items={data.hotThemes}
          color="amber"
        />
        <InfoCell
          icon={<ChevronRight className="w-3 h-3 text-cyan-400" />}
          title="推荐策略"
          items={data.recommendedStrategies}
          color="cyan"
        />
      </div>

      {/* 操作建议 */}
      <div className="p-3 bg-[#0a0f1a] rounded-lg border border-[#1a2235]">
        <p className="text-xs text-slate-400 leading-relaxed">{data.actionPlan}</p>
      </div>

      {/* 主要风险 */}
      {data.keyRisks.length > 0 && (
        <div className="space-y-1">
          {data.keyRisks.map((r, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <span className="text-[10px] text-red-400 mt-0.5">⚠</span>
              <span className="text-[10px] text-slate-500">{r}</span>
            </div>
          ))}
        </div>
      )}

      {/* 底部元数据 */}
      <div className="flex items-center justify-between text-[9px] text-slate-600">
        <span>生成引擎: {data.generatedBy === "multi-agent" ? "多Agent协作" : "规则合成"}</span>
        <span>温度: {data.temperatureScore}/100</span>
      </div>
    </div>
  );
}

function InfoCell({
  icon,
  title,
  items,
  color,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  color: string;
}) {
  return (
    <div className="p-2 bg-[#0a0f1a] rounded-lg border border-[#1a2235]">
      <div className="flex items-center gap-1 mb-1.5">
        {icon}
        <span className="text-[10px] text-slate-400">{title}</span>
      </div>
      <div className="space-y-0.5">
        {items.length > 0 ? (
          items.slice(0, 3).map((item, i) => (
            <div key={i} className={`text-[10px] text-${color}-400/80 truncate`}>
              {item}
            </div>
          ))
        ) : (
          <div className="text-[10px] text-slate-600">—</div>
        )}
      </div>
    </div>
  );
}
