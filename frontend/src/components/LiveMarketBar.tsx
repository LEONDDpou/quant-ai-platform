"use client";

import { useMarketSocket } from "@/hooks/useMarketSocket";

/**
 * 实时行情条：通过 WebSocket 订阅后端 /ws/paper/market 推送，
 * 展示关注池标的的最新价、涨跌幅与数据源（tencent/mock）。
 *
 * UI 状态管理（要求：加载中 / 数据正常 / 数据异常）：
 * - connecting：连接中，显示加载指示，不阻塞页面；
 * - open：正常，展示实时报价与数据源徽标；
 * - error：异常，显示友好告警 + 「重试」按钮（调用 retry() 立即重连）。
 * WS 不可用时静默降级（不崩溃、不阻塞），由后端在网络异常时回退模拟数据。
 */
export function LiveMarketBar() {
  const { quotes, status, error, lastTs, retry } = useMarketSocket();

  // 异常态：友好提示 + 重试
  if (status === "error") {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        <span className="text-amber-300">
          {error || "实时行情连接异常"}
        </span>
        <button
          onClick={retry}
          className="ml-1 px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 hover:bg-amber-500/30 transition"
        >
          重试
        </button>
      </div>
    );
  }

  // 连接中：加载指示
  if (status === "connecting" || !quotes || quotes.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <span className="inline-block w-2 h-2 rounded-full bg-slate-500 animate-pulse" />
        {status === "connecting"
          ? "实时行情连接中…"
          : "实时行情加载中…"}
      </div>
    );
  }

  // 正常态：实时报价 + 数据源徽标
  const dot = status === "open" ? "bg-emerald-400" : "bg-slate-500";
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
      <span className={`inline-block w-2 h-2 rounded-full ${dot}`} />
      {quotes.slice(0, 10).map((q) => {
        const up = q.changePct >= 0;
        return (
          <span key={q.code} className="flex items-center gap-1 whitespace-nowrap">
            <b className="text-slate-200">{q.name}</b>
            <span className="text-slate-300">{q.price?.toFixed(2)}</span>
            <span className={up ? "text-red-400" : "text-green-400"}>
              {up ? "+" : ""}
              {q.changePct?.toFixed(2)}%
            </span>
            <span
              className={`text-[10px] px-1 rounded ${
                q.dataSource === "tencent"
                  ? "text-emerald-300 bg-emerald-500/10"
                  : "text-slate-400 bg-slate-500/10"
              }`}
              title={q.dataSource === "tencent" ? "腾讯自选股实时数据" : "模拟数据（实时源暂不可用）"}
            >
              {q.dataSource}
            </span>
          </span>
        );
      })}
      {lastTs && (
        <span className="text-[10px] text-slate-600">更新于 {lastTs.slice(11)}</span>
      )}
    </div>
  );
}
