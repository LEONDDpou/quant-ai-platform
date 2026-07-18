"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

interface Props {
  data: { name: string; value: number; color: string }[];
  height?: number;
}

export function PositionPieChart({ data, height = 260 }: Props) {
  const option: EChartsOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "#1a1f2e",
      borderColor: "#2a3142",
      textStyle: { color: "#e2e8f0", fontSize: 12 },
      formatter: "{b}: {c}%",
    },
    legend: {
      type: "scroll",
      orient: "vertical",
      right: 0,
      top: "center",
      textStyle: { color: "#94a3b8", fontSize: 11 },
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 8,
    },
    series: [
      {
        type: "pie",
        radius: ["45%", "70%"],
        center: ["35%", "50%"],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 4, borderColor: "#0b0f19", borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: "bold", color: "#e2e8f0" },
        },
        data: data.map((d) => ({
          name: d.name,
          value: d.value,
          itemStyle: { color: d.color },
        })),
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: `${height}px`, width: "100%" }} />;
}
