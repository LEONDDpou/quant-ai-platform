"use client";

import { X, Sparkles, RefreshCw } from "lucide-react";
import { DimensionScoreBar } from "./DimensionScoreBar";
import { cn } from "@/lib/utils";

export interface SignalData {
  symbol: string;           // e.g. "600519.SH"
  name: string;             // e.g. "贵州茅台"
  direction: "buy" | "sell" | "hold";
  currentPrice: number;
  confidence: number;       // 0-100
  summary: string;          // AI decision summary
  dimensions: {
    name: string;
    score: number;
    detail: string;
  }[];
  riskLevel: "低" | "中" | "高";
  stopLoss?: number;
  targetPrice?: number;
}

interface SignalModalProps {
  signal: SignalData;
  onClose: () => void;
  onAction?: () => void;
}

export function SignalModal({ signal, onClose, onAction }: SignalModalProps) {
  const s = signal;

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-content p-5 animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-cyan-400" />
            <span className="text-sm font-semibold text-slate-200">AI交易决策情报</span>
          </div>
          <button onClick={onClose} className="btn-icon">
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>

        {/* Symbol + Price + Confidence */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-lg font-bold text-slate-100">{s.symbol}</span>
            <span className={cn("badge",
              s.direction === "buy" ? "badge-bullish" : s.direction === "sell" ? "badge-bearish" : "badge-neutral"
            )}>
              {s.direction === "buy" ? "买入" : s.direction === "sell" ? "卖出" : "持有"}
            </span>
          </div>
          <div className="text-right">
            <div className="text-[11px] text-slate-500">信号置信度</div>
            <div className={cn("font-mono font-bold text-xl",
              s.confidence >= 80 ? "text-emerald-400" : s.confidence >= 60 ? "text-cyan-400" : "text-amber-400"
            )}>
              {s.confidence}%
            </div>
          </div>
        </div>

        <div className="text-xs text-slate-400 mb-1">
          现价 <span className="font-mono text-slate-200">${s.currentPrice.toFixed(2)}</span>
        </div>

        {/* AI Summary */}
        <div className="bg-cyan-900/10 border border-cyan-900/25 rounded-lg px-3 py-2.5 mb-4">
          <div className="flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-slate-300 leading-relaxed">{s.summary}</p>
          </div>
        </div>

        {/* Dimensions */}
        <div className="mb-4">
          <div className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1">
            核心维度评分分析
          </div>
          <div className="bg-[#0d1220] rounded-lg p-3 space-y-0.5 border border-[#1a2235]">
            <div className="grid grid-cols-[80px_48px_1fr] gap-x-2 text-[10px] text-slate-600 pb-1.5 border-b border-[#1a2235]">
              <span>分析维度</span>
              <span className="text-center">AI评分</span>
              <span>详细依据</span>
            </div>
            {s.dimensions.map((dim) => (
              <DimensionScoreBar key={dim.name} {...dim} />
            ))}
          </div>
        </div>

        {/* Risk + Prices */}
        <div className="flex items-center justify-between mb-5 pt-3 border-t border-[#1e2a3d]">
          <div>
            <span className="text-[11px] text-slate-500">风险评级</span>
            <span className={cn("badge ml-2",
              s.riskLevel === "低" ? "badge-green" : s.riskLevel === "中" ? "badge-yellow" : "badge-red"
            )}>
              {s.riskLevel}
            </span>
          </div>
          {(s.stopLoss || s.targetPrice) && (
            <div className="flex items-center gap-6">
              {s.stopLoss && (
                <div className="text-right">
                  <div className="text-[10px] text-slate-500">止损价</div>
                  <div className="font-mono font-bold text-sm text-red-400">${s.stopLoss.toFixed(2)}</div>
                </div>
              )}
              {s.targetPrice && (
                <div className="text-right">
                  <div className="text-[10px] text-slate-500">目标价</div>
                  <div className="font-mono font-bold text-sm text-emerald-400">${s.targetPrice.toFixed(2)}</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* CTA */}
        <button
          onClick={() => { onAction?.(); onClose(); }}
          className="btn-primary w-full py-2.5 flex items-center justify-center gap-2 text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          按此信号交易
        </button>

        <button onClick={onClose} className="btn-ghost w-full text-center mt-2 text-xs text-slate-500">
          关闭报告
        </button>
      </div>
    </div>
  );
}
