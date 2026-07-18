"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

interface Props {
  score: number;
  height?: number;
}

export function SentimentGauge({ score, height = 200 }: Props) {
  const getColor = (s: number) => {
    if (s >= 70) return "#4ade80";
    if (s >= 50) return "#facc15";
    if (s >= 30) return "#f87171";
    return "#ef4444";
  };

  const option: EChartsOption = {
    backgroundColor: "transparent",
    series: [
      {
        type: "gauge",
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        radius: "90%",
        center: ["50%", "60%"],
        progress: {
          show: true,
          width: 12,
          roundCap: true,
          itemStyle: { color: getColor(score) },
        },
        axisLine: {
          lineStyle: { width: 12, color: [[1, "#1a1f2e"]] },
        },
        pointer: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
        anchor: { show: false },
        title: { show: false },
        detail: {
          valueAnimation: true,
          fontSize: 36,
          fontWeight: "bold",
          color: getColor(score),
          offsetCenter: [0, "10%"],
          formatter: "{value}",
        },
        data: [{ value: score }],
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: `${height}px`, width: "100%" }} />;
}
