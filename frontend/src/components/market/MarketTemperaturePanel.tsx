"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/config";
import { MarketThermometer } from "@/components/ui/MarketThermometer";
import { AIMarketJudgment } from "@/components/ui/AIMarketJudgment";
import { Calendar, Activity } from "lucide-react";

interface TempPoint {
  date: string;
  score: number;
  valuation: number;
  sentiment: number;
  capital: number;
  technical: number;
  riskLevel: string;
}

// 市场温度面板：合并自原独立页面 /market-temperature。
// 数据接口与交互逻辑原样保留（温度计/AI研判各自组件内拉取，历史曲线在此拉取）。
export default function MarketTemperaturePanel() {
  const [history, setHistory] = useState<TempPoint[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/market-temperature/history?days=30`)
      .then((r) => r.json())
      .then((data) => setHistory(data.temperature || []))
      .catch(console.error)
      .finally(() => setLoadingHistory(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* 上半部分：温度计 + AI研判 并排 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MarketThermometer />
        <AIMarketJudgment />
      </div>

      {/* 下半部分：历史温度曲线 */}
      <div className="bg-[#0d1220] border border-[#1a2235] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Calendar className="w-4 h-4 text-slate-500" />
          <h3 className="text-sm font-semibold text-slate-200">历史温度曲线（近30天）</h3>
        </div>

        {loadingHistory ? (
          <div className="animate-pulse space-y-3">
            <div className="h-[200px] bg-[#1a2235] rounded" />
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-8 text-slate-600 text-sm">
            暂无历史数据（首次计算后次日可见）
          </div>
        ) : (
          <HistoryChart data={history} />
        )}
      </div>

      {/* 免责声明 */}
      <div className="text-[10px] text-slate-600 text-center pb-4">
        ⚠️ 以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。投资有风险，决策需谨慎。
      </div>
    </div>
  );
}

// ============================================================
// 简易历史曲线（纯 CSS + SVG，不依赖 ECharts）
// ============================================================
function HistoryChart({ data }: { data: TempPoint[] }) {
  const w = 600;
  const h = 200;
  const pad = { top: 20, right: 20, bottom: 30, left: 40 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  const scores = data.map((d) => d.score);
  const minS = Math.min(...scores, 0);
  const maxS = Math.max(...scores, 100);
  const range = maxS - minS || 1;

  const xScale = (i: number) => pad.left + (i / Math.max(data.length - 1, 1)) * plotW;
  const yScale = (v: number) => pad.top + plotH - ((v - minS) / range) * plotH;

  // SVG path for score line
  const pathD = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(d.score)}`)
    .join(" ");

  // Risk zone fills
  const riskZones = [
    { y0: 0, y1: 30, color: "rgba(59,130,246,0.08)" },
    { y0: 30, y1: 50, color: "rgba(34,197,94,0.06)" },
    { y0: 50, y1: 70, color: "rgba(234,179,8,0.04)" },
    { y0: 70, y1: 85, color: "rgba(249,115,22,0.06)" },
    { y0: 85, y1: 100, color: "rgba(239,68,68,0.08)" },
  ];

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 220 }}>
        {/* Risk zones */}
        {riskZones.map((z, i) => (
          <rect
            key={i}
            x={pad.left}
            y={yScale(z.y1)}
            width={plotW}
            height={yScale(z.y0) - yScale(z.y1)}
            fill={z.color}
          />
        ))}

        {/* Grid lines */}
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line
              x1={pad.left}
              y1={yScale(v)}
              x2={w - pad.right}
              y2={yScale(v)}
              stroke="#1a2235"
              strokeWidth={v === 50 ? 1 : 0.5}
              strokeDasharray={v === 50 ? "" : "4 4"}
            />
            <text
              x={pad.left - 5}
              y={yScale(v) + 4}
              textAnchor="end"
              fill="#64748b"
              fontSize={9}
            >
              {v}
            </text>
          </g>
        ))}

        {/* Score line */}
        <path d={pathD} fill="none" stroke="#60a5fa" strokeWidth={2} strokeLinejoin="round" />

        {/* Data points */}
        {data.map((d, i) => (
          <circle
            key={i}
            cx={xScale(i)}
            cy={yScale(d.score)}
            r={2.5}
            fill={getScoreColor(d.score)}
            stroke="#0d1220"
            strokeWidth={1}
          />
        ))}

        {/* X-axis date labels (show every 5 days) */}
        {data
          .filter((_, i) => i % 5 === 0 || i === data.length - 1)
          .map((d, i) => {
            const idx = data.indexOf(d);
            return (
              <text
                key={i}
                x={xScale(idx)}
                y={h - 5}
                textAnchor="middle"
                fill="#475569"
                fontSize={8}
              >
                {d.date.slice(5)}
              </text>
            );
          })}
      </svg>
    </div>
  );
}

function getScoreColor(score: number): string {
  if (score < 30) return "#3b82f6";
  if (score < 50) return "#22c55e";
  if (score < 70) return "#eab308";
  if (score < 85) return "#f97316";
  return "#ef4444";
}
