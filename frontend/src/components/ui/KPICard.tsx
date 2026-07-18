"use client";

import { cn } from "@/lib/utils";
import { MiniSparkline } from "@/components/charts/MiniSparkline";

interface KPICardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  positive?: boolean;
  sparklineData?: number[];
  sparklineColor?: string;
  trend?: "up" | "down" | "flat";
  className?: string;
}

export function KPICard({
  icon,
  label,
  value,
  sub,
  positive,
  sparklineData,
  sparklineColor,
  trend,
  className,
}: KPICardProps) {
  const color = positive === undefined ? (positive !== false) : positive;
  const sc = sparklineColor ?? (color ? "#34d399" : "#f87171");

  return (
    <div className={cn("card-flat flex items-start gap-3", className)}>
      <div className="w-9 h-9 rounded-lg bg-[#1a2235] border border-[#253247] flex items-center justify-center text-slate-400 flex-shrink-0">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="metric-label">{label}</div>
        <div className="font-mono font-bold text-lg text-slate-100">{value}</div>
        {(sub || sparklineData) && (
          <div className="flex items-center gap-2 mt-0.5">
            {sub && (
              <span className={cn("metric-sub font-mono text-[11px]", color ? "pos" : "neg")}>
                {sub}
              </span>
            )}
          </div>
        )}
      </div>
      {sparklineData && sparklineData.length > 0 && (
        <MiniSparkline data={sparklineData} color={sc} height={32} />
      )}
    </div>
  );
}
