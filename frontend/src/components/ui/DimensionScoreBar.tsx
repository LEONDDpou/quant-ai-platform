"use client";

import { cn } from "@/lib/utils";

interface DimensionScoreBarProps {
  name: string;          // e.g. "技术分析"
  score: number;         // 0-100
  detail: string;        // description text
}

/**
 * Horizontal bar with score, used in AI signal modal for dimension scoring.
 * Color transitions: <40 red, 40-60 yellow, >60 green, >80 cyan
 */
export function DimensionScoreBar({ name, score, detail }: DimensionScoreBarProps) {
  const s = Math.max(0, Math.min(100, score));
  let color: string;
  if (s >= 80) color = "#22d3ee";    // cyan
  else if (s >= 60) color = "#34d399"; // green
  else if (s >= 40) color = "#fbbf24"; // yellow
  else color = "#f87171";             // red

  return (
    <div className="flex items-center gap-3 py-2">
      {/* Name */}
      <div className="w-20 text-xs text-slate-300 font-medium flex-shrink-0">{name}</div>
      
      {/* Score + Bar */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <span className={cn("font-mono font-bold text-sm w-7 text-right", 
          s >= 80 ? "text-cyan-400" : s >= 60 ? "text-emerald-400" : s >= 40 ? "text-amber-400" : "text-red-400"
        )}>
          {s}
        </span>
        <div className="score-bar-track">
          <div className="score-bar-fill" style={{ width: `${s}%`, backgroundColor: color }} />
        </div>
      </div>

      {/* Detail */}
      <div className="text-[11px] text-slate-500 hidden lg:block max-w-[280px] truncate">{detail}</div>
    </div>
  );
}
