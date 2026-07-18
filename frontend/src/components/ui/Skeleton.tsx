"use client";

import { cn } from "@/lib/utils";

/** 通用骨架屏脉冲组件 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-lg bg-slate-800/60",
        className,
      )}
    />
  );
}

/** 卡片骨架屏 — 标题栏 + 内容区 */
export function SkeletonCard({
  className,
  rows = 3,
}: {
  className?: string;
  rows?: number;
}) {
  return (
    <div
      className={cn(
        "bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden",
        className,
      )}
    >
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Skeleton className="w-4 h-4 rounded" />
        <Skeleton className="w-20 h-3.5" />
      </div>
      {/* 内容 */}
      <div className="p-4 space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="w-full h-5" />
        ))}
      </div>
    </div>
  );
}

/** 大盘骨架屏 — 模拟 IndexTicker */
export function SkeletonTicker() {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#151d2e]">
        <Skeleton className="w-4 h-4 rounded" />
        <Skeleton className="w-24 h-3.5" />
      </div>
      <div className="flex gap-4 px-4 py-3 overflow-x-auto">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex-shrink-0 w-28 space-y-2">
            <Skeleton className="w-14 h-3" />
            <Skeleton className="w-20 h-5" />
            <Skeleton className="w-12 h-3" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** 市场宽度骨架屏 */
export function SkeletonBreadth() {
  return (
    <div className="bg-[#0a0e1a] border border-[#151d2e] rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#151d2e]">
        <Skeleton className="w-4 h-4 rounded" />
        <Skeleton className="w-20 h-3.5" />
      </div>
      <div className="p-4">
        <div className="grid grid-cols-3 gap-3 mb-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="space-y-1.5 text-center">
              <Skeleton className="w-8 h-3 mx-auto" />
              <Skeleton className="w-12 h-6 mx-auto" />
            </div>
          ))}
        </div>
        <Skeleton className="w-full h-3 rounded-full" />
      </div>
    </div>
  );
}
