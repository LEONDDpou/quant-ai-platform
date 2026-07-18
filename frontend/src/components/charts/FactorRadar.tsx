"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

export interface FactorRadarData {
  dimensions: { label: string; score: number }[];
  totalScore: number;
  name: string;
}

export function FactorRadar({ data }: { data: FactorRadarData | null }) {
  if (!data || !data.dimensions.length) {
    return (
      <div className="flex items-center justify-center h-[280px] text-slate-500 text-sm">
        暂无因子评分数据
      </div>
    );
  }

  const maxScore = 100;
  const indicators = data.dimensions.map((d) => ({
    name: `${d.label}\n${d.score}`,
    max: maxScore,
  }));

  const option: EChartsOption = {
    backgroundColor: "transparent",
    radar: {
      center: ["50%", "52%"],
      radius: "65%",
      indicator: indicators,
      axisName: {
        color: "#8b9dc3",
        fontSize: 11,
        padding: [2, 0],
      },
      splitArea: {
        areaStyle: { color: ["transparent"] },
      },
      splitLine: { lineStyle: { color: "#1e2a3d" } },
      axisLine: { lineStyle: { color: "#1e2a3d" } },
    },
    series: [
      {
        type: "radar",
        symbol: "none",
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(59, 130, 246, 0.35)" },
              { offset: 1, color: "rgba(59, 130, 246, 0.05)" },
            ],
          },
        },
        lineStyle: { color: "#3b82f6", width: 2 },
        itemStyle: { color: "#3b82f6" },
        data: [{ value: data.dimensions.map((d) => d.score), name: data.name }],
      },
    ],
    tooltip: {
      backgroundColor: "#111827",
      borderColor: "#1e2a3d",
      textStyle: { color: "#e8edf5", fontSize: 11 },
    },
  };

  return (
    <div className="relative">
      <ReactECharts option={option} style={{ height: 280 }} notMerge />
      <div className="absolute top-2 right-3 text-sm font-mono text-blue-400">
        {data.totalScore.toFixed(0)}
        <span className="text-slate-500 text-xs">/100</span>
      </div>
    </div>
  );
}
