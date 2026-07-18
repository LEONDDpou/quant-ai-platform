"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/config";

// 后端 /ws/paper/market 推送的实时行情条目（与 MarketProvider.quote 同源结构）
export interface LiveQuote {
  code: string;
  name: string;
  price: number;
  changePct: number;
  change: number;
  volume: number;
  amount: number;
  turnover: number;
  amplitude: number;
  dataSource: string;
}

// 连接状态：connecting=连接中 / open=已连接正常 / error=异常（已断开，等待重连或手动重试）
export type ConnStatus = "connecting" | "open" | "error";

export interface MarketSocketState {
  quotes: LiveQuote[];
  status: ConnStatus;
  error: string | null;
  connected: boolean;
  lastTs: string | null;
  retry: () => void;
}

/**
 * 订阅后端 /ws/paper/market 实时行情（腾讯自选股真实源，后端批量拉取+共享缓存）。
 *
 * 连接与容错策略：
 * - 连接即发送 subscribe channel=all，接收关注池全部标的实时报价；
 * - 指数退避自动重连（1s→2s→4s→8s→上限 10s），网络抖动无需人工干预；
 * - 任何异常统一进入 error 态，暴露 retry() 供 UI 提供「重试」按钮；
 * - tick 为空 / 未连接时不抛错、不阻塞渲染，交由调用方降级展示。
 */
export function useMarketSocket(): MarketSocketState {
  const [quotes, setQuotes] = useState<LiveQuote[]>([]);
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastTs, setLastTs] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedByUs = useRef(false);
  const attemptRef = useRef(0);
  const connectRef = useRef<() => void>(() => {});

  useEffect(() => {
    const connect = () => {
      // 后端 WebSocket 地址需指向 API_BASE（后端 8000），而非前端 3000。
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
      try {
        ws = new WebSocket(`${proto}://${host}/ws/paper/market`);
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
        // 订阅全部标的（共享缓存，后端仅拉一次全量，订阅方越多越划算）
        try {
          ws.send(JSON.stringify({ action: "subscribe", channel: "all" }));
        } catch {
          /* ignore */
        }
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
          if (d.type === "paper_market_tick" && Array.isArray(d.quotes)) {
            setQuotes(d.quotes as LiveQuote[]);
            setLastTs(d.ts);
            setStatus("open");
            setError(null);
          }
        } catch {
          /* ignore malformed */
        }
      };
    };

    const scheduleReconnect = () => {
      if (closedByUs.current) return;
      const attempt = attemptRef.current++;
      // 指数退避：1s, 2s, 4s, 8s, 10s(封顶)
      const delays = [1000, 2000, 4000, 8000, 10000];
      const delay = delays[Math.min(attempt, delays.length - 1)];
      setStatus("error");
      setError(
        attempt === 0
          ? "实时行情连接失败，正在重连…"
          : `实时行情连接中断，第 ${attempt + 1} 次重连中…`
      );
      if (retryTimer.current) clearTimeout(retryTimer.current);
      retryTimer.current = setTimeout(connect, delay);
    };

    connectRef.current = connect;
    connect();

    return () => {
      closedByUs.current = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      wsRef.current?.close();
    };
  }, []);

  // 手动重试：立即重连并重置退避计数
  const retry = () => {
    if (retryTimer.current) clearTimeout(retryTimer.current);
    attemptRef.current = 0;
    closedByUs.current = false;
    try {
      wsRef.current?.close();
    } catch {
      /* ignore */
    }
    connectRef.current();
  };

  return { quotes, status, error, connected, lastTs, retry };
}
