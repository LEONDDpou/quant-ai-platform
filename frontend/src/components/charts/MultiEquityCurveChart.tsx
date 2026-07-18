"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

export interface EquitySeries {
  name: string;
  color: string;
  points: { date: string; value: number }[];
}

interface Props {
  series: EquitySeries[];
  height?: number;
}

// 多策略净值对比曲线（复用回测页设计语言）
export function MultiEquityCurveChart({ series, height = 320 }: Props) {
  // 统一日期轴（各策略用相同标的/区间，日期基本一致；取并集保证对齐）
  const dateSet = new Set<string>();
  series.forEach((s) => s.points.forEach((p) => dateSet.add(p.date)));
  const dates = Array.from(dateSet).sort();
  const dateToIdx = new Map(dates.map((d, i) => [d, i]));

  const echSeries = series.map((s) => {
    const vals = new Array(dates.length).fill(null);
    s.points.forEach((p) => {
      const i = dateToIdx.get(p.date);
      if (i !== undefined) vals[i] = p.value;
    });
    return {
      name: s.name,
      type: "line" as const,
      data: vals,
      smooth: true,
      symbol: "none" as const,
      lineStyle: { color: s.color, width: 2 },
      itemStyle: { color: s.color },
    };
  });

  const option: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 36, right: 20, bottom: 30, left: 60 },
    legend: {
      top: 4,
      textStyle: { color: "#94a3b8", fontSize: 10 },
      icon: "roundRect",
      itemWidth: 12,
      itemHeight: 4,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#1a1f2e",
      borderColor: "#2a3142",
      textStyle: { color: "#e2e8f0", fontSize: 12 },
    },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: { lineStyle: { color: "#2a3142" } },
      axisLabel: { color: "#64748b", fontSize: 10, formatter: (v: string) => v.slice(5) },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#1a1f2e" } },
      axisLabel: {
        color: "#64748b",
        fontSize: 10,
        formatter: (v: number) => (v >= 10000 ? (v / 10000).toFixed(0) + "万" : v.toString()),
      },
    },
    series: echSeries,
  };

  return <ReactECharts option={option} style={{ height: `${height}px`, width: "100%" }} notMerge />;
}
