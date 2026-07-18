"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export interface NewsItemCardData {
  id: string;
  title: string;
  source: string;
  time: string;
  sentiment: "positive" | "negative" | "neutral";
  impact: number;       // e.g. +4.6 or -3.2
  summary?: string;
  tags?: string[];
}

interface NewsItemCardProps {
  item: NewsItemCardData;
  onClick?: (id: string) => void;
}

export function NewsItemCard({ item, onClick }: NewsItemCardProps) {
  const isPos = item.sentiment === "positive";
  const isNeg = item.sentiment === "negative";

  return (
    <div
      onClick={() => onClick?.(item.id)}
      className="bg-[#0d1220] rounded-lg p-3.5 hover:bg-[#111a2b] transition-colors cursor-pointer border border-transparent hover:border-[#1e2a3d]"
    >
      <div className="flex items-start gap-3">
        {/* Sentiment score badge */}
        <span className={cn(
          "font-mono font-bold text-xs px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5",
          isPos ? "sent-pos" : isNeg ? "sent-neg" : "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono bg-slate-600/20 text-slate-400"
        )}>
          {isPos && <TrendingUp className="w-3 h-3 inline mr-0.5" />}
          {isNeg && <TrendingDown className="w-3 h-3 inline mr-0.5" />}
          {!isPos && !isNeg && <Minus className="w-3 h-3 inline mr-0.5" />}
          {item.impact > 0 ? `+${item.impact}` : item.impact}
        </span>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <h3 className="text-sm text-slate-200 leading-snug line-clamp-2">{item.title}</h3>
          {item.summary && (
            <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">{item.summary}</p>
          )}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className="text-[10px] text-slate-600">{item.source}</span>
            <span className="text-[10px] text-slate-700">{item.time}</span>
            {item.tags?.map((tag) => (
              <span key={tag} className={cn(
                "badge text-[10px]",
                isPos ? "badge-green" : isNeg ? "badge-red" : "badge-gray"
              )}>
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
