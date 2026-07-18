"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

interface Props {
  data: number[];
  color?: string;
  height?: number;
}

export function MiniSparkline({ data, color = "#4ade80", height = 40 }: Props) {
  const option: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 2, right: 0, bottom: 2, left: 0 },
    xAxis: { type: "category", show: false, data: data.map((_, i) => i) },
    yAxis: { type: "value", show: false },
    series: [
      {
        type: "line",
        data,
        smooth: true,
        symbol: "none",
        lineStyle: { color, width: 1.5 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: color + "40" },
              { offset: 1, color: color + "00" },
            ],
          },
        },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: `${height}px`, width: "100%" }} />;
}
