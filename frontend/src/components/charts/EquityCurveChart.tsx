"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

interface Props {
  data: { date: string; value: number }[];
  height?: number;
}

export function EquityCurveChart({ data, height = 300 }: Props) {
  const option: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 20, right: 20, bottom: 30, left: 60 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#1a1f2e",
      borderColor: "#2a3142",
      textStyle: { color: "#e2e8f0", fontSize: 12 },
      formatter: (params: any) => {
        const p = params[0];
        return `${p.axisValue}<br/>资产: <span style="color:#60a5fa;font-weight:bold">¥${Number(p.value).toLocaleString()}</span>`;
      },
    },
    xAxis: {
      type: "category",
      data: data.map((d) => d.date),
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
    series: [
      {
        type: "line",
        data: data.map((d) => d.value),
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#3b82f6", width: 2 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(59,130,246,0.25)" },
              { offset: 1, color: "rgba(59,130,246,0.0)" },
            ],
          },
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: `${height}px`, width: "100%" }} />;
}
