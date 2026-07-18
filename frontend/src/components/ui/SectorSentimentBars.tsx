"use client";

import { cn } from "@/lib/utils";

interface SectorBarData {
  name: string;
  value: number;   // percentage
  color?: string;
}

interface SectorSentimentBarsProps {
  sectors: SectorBarData[];
  className?: string;
}

export function SectorSentimentBars({ sectors, className }: SectorSentimentBarsProps) {
  const maxVal = Math.max(...sectors.map((s) => Math.abs(s.value)), 1);

  return (
    <div className={cn("space-y-2", className)}>
      {sectors.map((s) => {
        const isPos = s.value >= 0;
        const widthPct = (Math.abs(s.value) / maxVal) * 100;
        const defaultColor = isPos ? "#34d399" : "#f87171";
        const color = s.color ?? defaultColor;

        return (
          <div key={s.name}>
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[11px] text-slate-400">{s.name}</span>
              <span className={cn("font-mono text-xs", isPos ? "pos" : "neg")}>
                {isPos ? "+" : ""}{s.value}%
              </span>
            </div>
            <div className="h-1.5 bg-[#0d1220] rounded-full overflow-hidden">
              <div
                className={cn("h-full rounded-full transition-all duration-500")}
                style={{ width: `${widthPct}%`, backgroundColor: color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
