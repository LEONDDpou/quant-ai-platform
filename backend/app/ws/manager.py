"""WebSocket 连接管理器 — 维护活动连接、订阅关系并定向推送。

设计要点（性能 + 订阅）：
- 每个连接可订阅若干标的代码，或订阅 ``__all__`` 表示接收全部；
- 推送循环调用 ``publish_market`` 时按订阅关系**逐连接过滤**，只发该连接
  关心的标的，避免向所有客户端广播全量行情造成带宽/CPU 浪费；
- 未显式订阅的连接默认接收 default_codes（保持历史行为，向后兼容）。
"""
from fastapi import WebSocket

# 订阅「全部标的」的哨兵值
SUB_ALL = "__all__"


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        # WebSocket -> 订阅代码集合（含可能的 SUB_ALL）
        self._subs: dict[WebSocket, set] = {}
        # WebSocket -> 是否已确定订阅意图（收到首条 subscribe/ping 或超时）
        # 未就绪前，publish_market 不会向该连接推送「默认全量」，避免
        # 客户端还没发 subscribe 就被先灌一帧整表快照。
        self._pending: dict[WebSocket, bool] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        self._subs[ws] = set()
        self._pending[ws] = True

    def init_done(self, ws: WebSocket) -> None:
        """标记该连接已完成首条消息处理（或等待超时），可参与正常推送。"""
        self._pending[ws] = False

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        self._subs.pop(ws, None)
        self._pending.pop(ws, None)

    # —— 订阅管理（由 WS 端点收到客户端消息时调用）——
    def subscribe(self, ws: WebSocket, codes) -> None:
        cur = self._subs.setdefault(ws, set())
        cur.update(str(c) for c in codes)

    def unsubscribe(self, ws: WebSocket, codes) -> None:
        cur = self._subs.get(ws)
        if cur:
            cur.difference_update(str(c) for c in codes)

    def has_sub(self, ws: WebSocket, code: str) -> bool:
        s = self._subs.get(ws)
        if not s:
            return False
        return SUB_ALL in s or code in s

    async def send_personal(self, ws: WebSocket, msg: dict):
        try:
            await ws.send_json(msg)
        except Exception:
            self.disconnect(ws)

    async def broadcast(self, msg: dict):
        """向所有连接广播；异常连接静默移除。"""
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def publish_market(self, quotes: dict, ts: str, default_codes: list) -> None:
        """按订阅关系向各连接定向推送行情。

        :param quotes: {code: quote_dict} 当前快照里的全部可用报价
        :param ts: 推送时间戳（ISO 字符串）
        :param default_codes: 未订阅连接默认接收的代码列表（watchlist）
        """
        dead = []
        for ws in list(self.active):
            # 尚未完成首条消息处理的连接，先不推送（避免未订阅即收到默认全量）
            if self._pending.get(ws, False):
                continue
            subs = self._subs.get(ws, set())
            if not subs:
                want = set(default_codes)
            elif SUB_ALL in subs:
                want = set(quotes.keys())
            else:
                want = subs
            payload = {
                "type": "paper_market_tick",
                "ts": ts,
                "quotes": [quotes[c] for c in want if c in quotes],
            }
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def count(self) -> int:
        return len(self.active)
