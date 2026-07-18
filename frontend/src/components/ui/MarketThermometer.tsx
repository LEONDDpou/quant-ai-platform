"use client";

import { useEffect, useState, useRef } from "react";
import { API_BASE } from "@/lib/config";

interface TemperatureData {
  score: number;
  riskLevel: string;
  riskLabel: string;
  valuation: { score: number; label: string; detail: Record<string, number> };
  sentiment: { score: number; label: string; detail: Record<string, number> };
  capital: { score: number; label: string; detail: Record<string, number> };
  technical: { score: number; label: string; detail: Record<string, number> };
}

export function MarketThermometer() {
  const [data, setData] = useState<TemperatureData | null>(null);
  const [loading, setLoading] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/market-temperature`)
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Draw arc gauge
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = 200;
    const h = 150;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const cx = w / 2;
    const cy = h;
    const radius = 120;
    const startAngle = Math.PI;
    const endAngle = 0;

    // Background arc
    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle, endAngle);
    ctx.lineWidth = 18;
    ctx.strokeStyle = "#1a2235";
    ctx.stroke();

    // Score arc (gradient: blue -> green -> yellow -> orange -> red)
    const score = data.score;
    const scoreAngle = startAngle + (score / 100) * Math.PI;
    const grad = ctx.createLinearGradient(0, cy - radius, w, cy);
    grad.addColorStop(0, "#3b82f6");
    grad.addColorStop(0.3, "#22c55e");
    grad.addColorStop(0.55, "#eab308");
    grad.addColorStop(0.8, "#f97316");
    grad.addColorStop(1, "#ef4444");

    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle, scoreAngle);
    ctx.lineWidth = 18;
    ctx.lineCap = "round";
    ctx.strokeStyle = grad;
    ctx.stroke();

    // Score text
    ctx.fillStyle = "#f1f5f9";
    ctx.font = "bold 36px 'JetBrains Mono', monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(`${Math.round(score)}`, cx, cy - 25);

    // Label
    ctx.font = "12px sans-serif";
    ctx.fillStyle = getRiskColor(data.riskLevel);
    ctx.fillText(data.riskLabel, cx, cy - 8);

    // Min/Max labels
    ctx.font = "9px sans-serif";
    ctx.fillStyle = "#64748b";
    ctx.textAlign = "left";
    ctx.fillText("0", 10, cy - 5);
    ctx.textAlign = "right";
    ctx.fillText("100", w - 10, cy - 5);
  }, [data]);

  if (loading) {
    return (
      <div className="bg-[#0d1220] border border-[#1a2235] rounded-xl p-5 animate-pulse">
        <div className="h-4 w-24 bg-[#1a2235] rounded mb-4" />
        <div className="h-[150px] bg-[#1a2235] rounded" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-[#0d1220] border border-[#1a2235] rounded-xl p-5">
        <div className="text-slate-500 text-sm">市场温度数据加载失败</div>
      </div>
    );
  }

  const dims = [
    { key: "valuation", label: "估值", score: data.valuation.score },
    { key: "sentiment", label: "情绪", score: data.sentiment.score },
    { key: "capital", label: "资金", score: data.capital.score },
    { key: "technical", label: "技术", score: data.technical.score },
  ] as const;

  return (
    <div className="bg-[#0d1220] border border-[#1a2235] rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-200">市场温度计</h3>
        <span
          className="text-[10px] px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: getRiskBg(data.riskLevel),
            color: getRiskColor(data.riskLevel),
          }}
        >
          {data.riskLabel}
        </span>
      </div>

      <canvas ref={canvasRef} className="w-full mb-3" />

      {/* 四维进度条 */}
      <div className="space-y-1.5">
        {dims.map((d) => (
          <div key={d.key} className="flex items-center gap-2">
            <span className="text-[10px] text-slate-500 w-8 text-right">{d.label}</span>
            <div className="flex-1 h-1.5 bg-[#1a2235] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${d.score}%`,
                  backgroundColor: getScoreColor(d.score),
                }}
              />
            </div>
            <span className="text-[10px] text-slate-400 w-7 text-right font-mono">
              {Math.round(d.score)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function getScoreColor(score: number): string {
  if (score < 30) return "#3b82f6";
  if (score < 50) return "#22c55e";
  if (score < 70) return "#eab308";
  if (score < 85) return "#f97316";
  return "#ef4444";
}

function getRiskColor(level: string): string {
  const colors: Record<string, string> = {
    extreme_low: "#3b82f6",
    low: "#22c55e",
    medium: "#eab308",
    high: "#f97316",
    extreme_high: "#ef4444",
  };
  return colors[level] || "#eab308";
}

function getRiskBg(level: string): string {
  const colors: Record<string, string> = {
    extreme_low: "rgba(59,130,246,0.15)",
    low: "rgba(34,197,94,0.15)",
    medium: "rgba(234,179,8,0.15)",
    high: "rgba(249,115,22,0.15)",
    extreme_high: "rgba(239,68,68,0.15)",
  };
  return colors[level] || "rgba(234,179,8,0.15)";
}
