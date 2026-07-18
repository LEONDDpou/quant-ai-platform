"use client";

import { cn } from "@/lib/utils";

interface SentimentGaugeProps {
  score: number;       // 0-100
  size?: number;        // diameter in px
  showLabel?: boolean;
}

/**
 * SVG-based semi-circular sentiment gauge.
 * Score 0-50 = red zone, 50-70 = yellow, 70-100 = green
 */
export function SentimentGauge({ score, size = 160, showLabel = true }: SentimentGaugeProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = (size - 16) / 2;
  const cx = size / 2;
  const cy = size / 2 + 4;
  // Semi-circle arc: from left (-180deg) to right (0deg) in SVG coordinates
  // We draw from PI to 0 (counter-clockwise in SVG)
  const startAngle = Math.PI;
  const endAngle = 0;
  const arcLength = Math.PI * radius;

  // Progress angle
  const progressAngle = Math.PI * (clamped / 100);
  // The filled arc goes from PI to (PI - progressAngle)
  const largeArc = clamped > 50 ? 1 : 0;

  // Path for background track
  const trackX1 = cx + radius * Math.cos(Math.PI);
  const trackY1 = cy + radius * Math.sin(Math.PI);
  const trackX2 = cx + radius * Math.cos(0);
  const trackY2 = cy + radius * Math.sin(0);
  const trackD = `M ${trackX1} ${trackY1} A ${radius} ${radius} 0 1 1 ${trackX2} ${trackY2}`;

  // Path for value arc
  const valEndX = cx + radius * Math.cos(Math.PI - progressAngle);
  const valEndY = cy + radius * Math.sin(Math.PI - progressAngle);
  const valD = `M ${trackX1} ${trackY1} A ${radius} ${radius} 0 ${largeArc} 1 ${valEndX} ${valEndY}`;

  // Color based on score
  let color: string;
  if (clamped >= 70) color = "#34d399";
  else if (clamped >= 45) color = "#fbbf24";
  else color = "#f87171";

  // Tick marks
  const ticks = Array.from({ length: 11 }, (_, i) => {
    const a = Math.PI - (Math.PI * i) / 10;
    const innerR = radius - 8;
    const outerR = radius + 2;
    return {
      x1: cx + innerR * Math.cos(a),
      y1: cy + innerR * Math.sin(a),
      x2: cx + outerR * Math.cos(a),
      y2: cy + outerR * Math.sin(a),
    };
  });

  return (
    <div className="flex flex-col items-center" style={{ width: size }}>
      <svg width={size} height={size * 0.6} viewBox={`0 0 ${size} ${size * 0.65}`}>
        {/* Track */}
        <path d={trackD} fill="none" stroke="#1e2a3d" strokeWidth={8} strokeLinecap="round" />
        {/* Value */}
        <path d={valD} fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
              style={{ transition: "stroke-dasharray 0.7s ease", filter: `drop-shadow(0 0 4px ${color}40)` }} />
        
        {/* Ticks */}
        {ticks.map((t, i) => (
          <line key={i} x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
                stroke={i === 5 ? "#475569" : "#253247"} strokeWidth={i % 5 === 0 ? 1.5 : 0.8} />
        ))}

        {/* Needle indicator dot at current position */}
        <circle cx={valEndX} cy={valEndY} r={3} fill={color}
                style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
      </svg>

      {/* Center text */}
      <div className="-mt-2 text-center">
        <div className={cn("font-mono font-bold text-3xl leading-none",
          clamped >= 70 ? "text-emerald-400" : clamped >= 45 ? "text-amber-400" : "text-red-400"
        )}>
          {Math.round(clamped)}
        </div>
        {showLabel && (
          <div className="text-[10px] text-slate-500 mt-0.5">
            {clamped >= 70 ? "偏多" : clamped >= 45 ? "中性" : "偏空"}
          </div>
        )}
      </div>
    </div>
  );
}
