"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { API_BASE } from "@/lib/config";
import type { MarketWSQuote } from "@/lib/api";

export type MarketConnStatus = "connecting" | "open" | "error";

export interface MarketRealtimeSocketState {
  quotes: MarketWSQuote[];
  byCode: Record<string, MarketWSQuote>;
  status: MarketConnStatus;
  error: string | null;
  connected: boolean;
  lastTs: string | null;
  retry: () => void;
}

/**
 * 订阅后端 /ws/market/realtime 实时行情推送（AI 量化实时数据支撑模块）。
 *
 * ⚠️ 关键：本 hook 经过「差异更新 + rAF 合帧」改造，专门消灭数据持续闪烁：
 *  - 每一帧仅对【真正变化】的 code 生成新对象引用，未变化的 code 复用旧引用；
 *  - 多帧推送在 1 个动画帧内合并为 1 次 setState，避免高频抖动；
 *  - 若一帧与上一帧数据完全一致，则【完全不触发渲染】，消费方不会无谓重绘；
 *  - 配合消费方的 React.memo（按 code 记忆），只有数值真的变了的行才会重渲染，
 *    从而做到"逐行平滑更新、整表不再整体闪一下"。
 *
 * 连接即接收一帧快照（后端 connect 时主动推一帧），之后按 settings.refresh_rate 周期广播；
 * 指数退避自动重连（1s→2s→4s→8s→上限 10s）；任何异常统一进入 error 态并暴露 retry()。
 */
export function useMarketRealtimeSocket(): MarketRealtimeSocketState {
  const [quotes, setQuotes] = useState<MarketWSQuote[]>([]);
  const [byCode, setByCode] = useState<Record<string, MarketWSQuote>>({});
  const [status, setStatus] = useState<MarketConnStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastTs, setLastTs] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedByUs = useRef(false);
  const attemptRef = useRef(0);
  const connectRef = useRef<() => void>(() => {});

  // 待提交的最新一帧（合帧用，仅保留最后一帧即可，因每帧都是全量快照）
  const pendingRef = useRef<MarketWSQuote[] | null>(null);
  const rafRef = useRef<number | null>(null);
  // 上一帧按 code 索引的行情引用，用于差异比较 + 复用未变引用
  const prevByCodeRef = useRef<Record<string, MarketWSQuote>>({});

  // 仅比较"会影响展示"的字段，决定是否真的变了
  const quoteChanged = useCallback((prev: MarketWSQuote | undefined, next: MarketWSQuote): boolean => {
    if (!prev) return true;
    return (
      prev.price !== next.price ||
      prev.change !== next.change ||
      prev.change_pct !== next.change_pct ||
      prev.volume !== next.volume ||
      prev.amount !== next.amount ||
      prev.turnover !== next.turnover ||
      prev.pe !== next.pe ||
      prev.pb !== next.pb ||
      prev.total_mv !== next.total_mv ||
      prev.float_mv !== next.float_mv ||
      prev.open !== next.open ||
      prev.high !== next.high ||
      prev.low !== next.low ||
      prev.prev_close !== next.prev_close
    );
  }, []);

  // 将 pending 帧与上一帧做差异比较，仅提交真正变化的部分
  const flush = useCallback(() => {
    rafRef.current = null;
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = null;

    const prev = prevByCodeRef.current;
    let changed = false;
    const next: Record<string, MarketWSQuote> = { ...prev };
    for (const q of pending) {
      if (quoteChanged(prev[q.code], q)) {
        next[q.code] = q; // 仅变化的 code 拿到新引用
        changed = true;
      }
    }
    if (!changed) return; // 完全没变 → 不 setState，杜绝无谓重绘/闪烁

    prevByCodeRef.current = next;
    setByCode(next);
    setQuotes(Object.values(next));
  }, [quoteChanged]);

  const scheduleFlush = useCallback(() => {
    if (rafRef.current != null) return; // 同帧内只排一次
    rafRef.current = requestAnimationFrame(flush);
  }, [flush]);

  useEffect(() => {
    const connect = () => {
      let host = window.location.host;
      try {
        const u = new URL(API_BASE);
        if (u.host) host = u.host;
      } catch {
        /* API_BASE 非法时回退到 window.location.host */
      }
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      setStatus("connecting");
      setError(null);

      let ws: WebSocket;
      const url = `${proto}://${host}/ws/market/realtime`;
      try {
        ws = new WebSocket(url);
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        attemptRef.current = 0;
        setConnected(true);
        setStatus("open");
        setError(null);
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs.current) {
          scheduleReconnect();
        }
      };

      ws.onerror = () => {
        setStatus("error");
        setError("实时行情连接异常，正在尝试重连…");
        try {
          ws.close();
        } catch {
          /* ignore */
        }
      };

      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          if (d.type === "market_realtime" && Array.isArray(d.quotes)) {
            // 仅缓存最新一帧，rAF 合帧后再做差异比较
            pendingRef.current = d.quotes as MarketWSQuote[];
            if (d.ts) setLastTs(d.ts);
            setStatus("open");
            setError(null);
            scheduleFlush();
          }
        } catch {
          /* ignore malformed */
        }
      };
    };

    const scheduleReconnect = () => {
      if (closedByUs.current) return;
      const attempt = attemptRef.current++;
      const delays = [1000, 2000, 4000, 8000, 10000];
      const delay = delays[Math.min(attempt, delays.length - 1)];
      setStatus("error");
      setError(
        attempt === 0
          ? "实时行情连接失败，正在重连…"
          : `实时行情连接中断，第 ${attempt + 1} 次重连中…`,
      );
      if (retryTimer.current) clearTimeout(retryTimer.current);
      retryTimer.current = setTimeout(connect, delay);
    };

    connectRef.current = connect;
    connect();

    return () => {
      closedByUs.current = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      wsRef.current?.close();
    };
  }, []);

  // 手动重试：立即重连并重置退避计数
  const retry = useCallback(() => {
    if (retryTimer.current) clearTimeout(retryTimer.current);
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    attemptRef.current = 0;
    closedByUs.current = false;
    try {
      wsRef.current?.close();
    } catch {
      /* ignore */
    }
    connectRef.current();
  }, []);

  return { quotes, byCode, status, error, connected, lastTs, retry };
}
