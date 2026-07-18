"""模拟盘交易系统 — M7 AI 自动交易核心服务。

职责：
1. 策略管理：列出 / 创建 / 启停 AI 交易策略（PaperStrategy）；
2. 决策引擎：基于实时行情 + 日 K 技术指标（双均线 / RSI / 突破）生成买卖/持有信号，
   信号落 Signal 表（source=ai）；
3. 自动下单：买入信号经 M5 前置风控后提交 source=ai 限价单（撮合逻辑复用 M3 引擎），
   成交后按策略参数为持仓回写止损/止盈价；
4. 自动平仓：监控持仓止损/止盈触发，提交条件单（stop_loss / stop_profit），
   由 M3 撮合循环完成平仓；
5. 日志与状态：AI 决策 / 交易写入 TradeLog，对外暴露运行状态。

设计约束（诚实简化，详见交付说明）：
- 决策为「确定性规则引擎」（非 LLM 实时推理），保证可复现、无外部依赖；
- 行情经 MarketProvider 接入（AKShare 真实源优先，外网受限自动回退模拟）；
- 仅对买入做强风控（复用 M5），卖出放行；所有 AI 单均经 OrderService 统一入口；
- 后台循环（main.py 的 _paper_ai_loop）每 ~30s 对启用策略跑一轮 run_once。
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.paper.domain_models import (
    PaperStrategy,
    Signal,
    PaperPosition,
    PaperOrder,
    PaperTrade,
)
from app.paper.repositories.account_repo import AccountRepository
from app.paper.repositories.strategy_repo import (
    StrategyRepository,
    SignalRepository,
    AILogRepository,
    WatchlistRepository,
)
from app.paper.services.order_repo import OrderRepository
from app.paper.services.position_repo import PositionRepository
from app.paper.services.market_provider import market_provider
from app.paper.services.order_service import OrderService
from app.paper.schemas import CreateOrderRequest
from app.paper.errors import PaperError

# 内置默认监控池（自选股池与策略 universe 均为空时的兜底）
DEFAULT_UNIVERSE = ["600519", "300750", "601318", "000858", "600036", "002594"]

# 策略默认参数
DEFAULT_STRATEGY_PARAMS = {
    "universe": [],          # 监控标的（空 → 用自选股池 → 再空 → 内置默认池）
    "maxPositions": 5,        # 最大持仓标的数
    "perTradePct": 0.15,      # 单笔占可用资金比例(0-1)
    "stopLossPct": 0.08,      # 止损幅度（相对成本）
    "takeProfitPct": 0.20,    # 止盈幅度（相对成本）
    "indicators": {"maFast": 5, "maSlow": 20, "rsiPeriod": 14,
                   "rsiOversold": 30, "rsiOverbought": 70},
    "breakoutWindow": 15,     # 近期高点窗口（根）
    "buyThreshold": 60,       # 综合评分买入阈值(0-100)
    "sellThreshold": 40,      # 综合评分卖出阈值(0-100)
    "autoSLTP": True,         # 自动为 AI 买入的持仓设置止损/止盈
}

# 运行态（供 auto_status 暴露，进程内有效）
_LAST_RUN: dict = {}      # account_id -> {at, summary, watched, running}


# ============================================================
# 技术指标
# ============================================================
def _ma(values: List[float], n: int) -> Optional[float]:
    if len(values) < n or n <= 0:
        return None
    return sum(values[-n:]) / n


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    gains = gains[-period:]
    losses = losses[-period:]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _highest(values: List[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    return max(values[-n:])


# ============================================================
# 服务
# ============================================================
class AutoTradeService:
    """AI 自动交易核心服务。"""

    def __init__(self):
        self.strategy_repo = StrategyRepository()
        self.signal_repo = SignalRepository()
        self.log_repo = AILogRepository()
        self.watch_repo = WatchlistRepository()
        self.position_repo = PositionRepository()
        self.order_repo = OrderRepository()
        self.account_repo = AccountRepository()
        self.order_svc = OrderService()

    # ——————————————————————— 策略管理 ———————————————————————
    def list_strategies(self, account_id: int) -> List[PaperStrategy]:
        return self.strategy_repo.list_by_account(account_id)

    def get_strategy(self, account_id: int, strategy_id: str) -> Optional[PaperStrategy]:
        return self.strategy_repo.get_by_account(account_id, strategy_id)

    def create_or_update_strategy(self, account_id: int, body: dict) -> PaperStrategy:
        """创建或更新策略。body: {id?, name, description?, enabled?, params?}。"""
        import uuid
        sid = body.get("id") or f"ai-{uuid.uuid4().hex[:8]}"
        existing = self.strategy_repo.get_by_account(account_id, sid)
        name = body.get("name") or (existing.name if existing else "AI 双均线+RSI 策略")
        description = body.get("description", existing.description if existing else "")
        enabled = bool(body.get("enabled", existing.enabled if existing else False))
        # 合并参数（用户参数覆盖默认）
        base = dict(DEFAULT_STRATEGY_PARAMS)
        if existing and isinstance(existing.params, dict):
            base.update(existing.params)
        if isinstance(body.get("params"), dict):
            base.update(body["params"])
        # 子字典 indicators 做深合并
        if isinstance(body.get("params", {}).get("indicators"), dict) and existing:
            merged = dict(DEFAULT_STRATEGY_PARAMS["indicators"])
            if isinstance(existing.params, dict) and isinstance(existing.params.get("indicators"), dict):
                merged.update(existing.params["indicators"])
            merged.update(body["params"]["indicators"])
            base["indicators"] = merged

        with SessionLocal() as db:
            if existing:
                obj = db.get(PaperStrategy, sid)
                obj.name = name
                obj.description = description
                obj.enabled = enabled
                obj.params = base
                obj.updated_at = datetime.utcnow()
            else:
                obj = PaperStrategy(
                    id=sid, account_id=account_id, name=name,
                    description=description, enabled=enabled, params=base, metrics={},
                )
                db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj

    def set_enabled(self, account_id: int, strategy_id: str, enabled: bool) -> PaperStrategy:
        with SessionLocal() as db:
            obj = db.get(PaperStrategy, strategy_id)
            if obj is None or obj.account_id != account_id:
                raise PaperError(f"策略不存在: {strategy_id}", "STRATEGY_NOT_FOUND")
            obj.enabled = bool(enabled)
            obj.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(obj)
            return obj

    # ——————————————————————— 决策引擎 ———————————————————————
    def decide(self, code: str, params: dict) -> dict:
        """基于行情 + 日 K 生成综合信号。返回供 Signal 表落库的字段字典。"""
        ind = params.get("indicators", DEFAULT_STRATEGY_PARAMS["indicators"])
        ma_fast_n = int(ind.get("maFast", 5))
        ma_slow_n = int(ind.get("maSlow", 20))
        rsi_period = int(ind.get("rsiPeriod", 14))
        rsi_ob = float(ind.get("rsiOverbought", 70))
        rsi_os = float(ind.get("rsiOversold", 30))
        breakout_window = int(params.get("breakoutWindow", 15))

        quote = market_provider.quote(code)
        price = float(quote.get("price") or 0.0)
        name = quote.get("name") or code

        kline = market_provider.kline(code, "day", limit=max(ma_slow_n + 10, 60))
        points = kline.get("points", [])
        closes = [float(p.get("close", 0.0)) for p in points]
        highs = [float(p.get("high", 0.0)) for p in points]

        # 数据不足 → 中性持有
        if price <= 0 or len(closes) < ma_slow_n + 2:
            return {
                "code": code, "name": name, "signal_type": "hold", "strength": 50.0,
                "source": "ai", "reason": "数据不足，保持观望",
                "price_target": 0.0, "stop_loss": 0.0, "take_profit": 0.0,
                "risk_score": 50.0, "score": 50.0,
            }

        ma_fast = _ma(closes, ma_fast_n)
        ma_slow = _ma(closes, ma_slow_n)
        rsi = _rsi(closes, rsi_period)
        recent_high = _highest(highs, breakout_window)
        avg_vol = (sum(p.get("volume", 0.0) for p in points[-breakout_window:]) / breakout_window
                   if breakout_window else 0.0)
        last_vol = float(points[-1].get("volume", 0.0)) if points else 0.0

        score = 50.0
        reasons = []
        # 趋势
        if ma_fast is not None and ma_slow is not None:
            if ma_fast > ma_slow:
                score += 15
                reasons.append(f"短均线({ma_fast_n})上穿长均线({ma_slow_n})，趋势向上")
            else:
                score -= 10
                reasons.append(f"短均线({ma_fast_n})位于长均线({ma_slow_n})下方，趋势偏弱")
        # RSI
        if rsi is not None:
            if rsi < rsi_os:
                score += 15
                reasons.append(f"RSI={rsi:.0f} 超卖(<%d)" % rsi_os)
            elif rsi > rsi_ob:
                score -= 15
                reasons.append(f"RSI={rsi:.0f} 超买(>%d)" % rsi_ob)
            else:
                reasons.append(f"RSI={rsi:.0f} 中性")
        # 突破
        if recent_high and price >= recent_high * (1 - 0.005):
            score += 12
            reasons.append("价格逼近/创近期新高，突破形态")
        # 量能确认
        if avg_vol > 0 and last_vol > avg_vol * 1.2:
            score += 5
            reasons.append("成交量放大，资金认可")

        score = max(0.0, min(100.0, score))
        buy_threshold = float(params.get("buyThreshold", 60))
        sell_threshold = float(params.get("sellThreshold", 40))

        if score >= buy_threshold:
            sig = "buy"
            strength = score
        elif score <= sell_threshold:
            sig = "sell"
            strength = 100.0 - score
        else:
            sig = "hold"
            strength = 50.0

        tp_pct = float(params.get("takeProfitPct", 0.20))
        sl_pct = float(params.get("stopLossPct", 0.08))
        price_target = round(price * (1 + tp_pct), 2) if sig != "hold" else 0.0
        take_profit = round(price * (1 + tp_pct), 2)
        stop_loss = round(price * (1 - sl_pct), 2)
        # 风险评分：RSI 极端 + 高位 → 风险高
        risk = 30.0
        if rsi is not None:
            risk += abs(rsi - 50) * 0.4
        if recent_high and price >= recent_high:
            risk += 10

        return {
            "code": code, "name": name, "signal_type": sig, "strength": round(strength, 1),
            "source": "ai", "reason": "；".join(reasons) or "综合指标中性",
            "price_target": price_target, "stop_loss": stop_loss,
            "take_profit": take_profit, "risk_score": round(min(100.0, risk), 1),
            "score": round(score, 1),
        }

    def _universe(self, account_id: int, params: dict) -> List[str]:
        u = params.get("universe") or []
        if isinstance(u, list) and u:
            return [str(c) for c in u]
        wl = self.watch_repo.list_codes(account_id)
        if wl:
            return wl
        return list(DEFAULT_UNIVERSE)

    # ——————————————————————— 运行一轮 ———————————————————————
    def run_once(self, account_id: int, strategy_id: Optional[str] = None) -> dict:
        """对账户跑一轮 AI 自动交易。返回本轮摘要字典。"""
        _LAST_RUN[account_id] = _LAST_RUN.get(account_id, {})
        _LAST_RUN[account_id]["running"] = True
        summary = {
            "accountId": account_id, "strategyId": None, "strategyName": None,
            "signals": 0, "buys": 0, "sells": 0, "stopTriggers": 0,
            "watched": 0, "skipped": 0, "logs": 0, "dataSource": "",
            "errors": [],
        }
        try:
            # 选定策略：指定 > 启用策略首条 > 无则报错返回
            strategy = None
            if strategy_id:
                strategy = self.strategy_repo.get_by_account(account_id, strategy_id)
            if strategy is None:
                enabled = self.strategy_repo.enabled_for_account(account_id)
                strategy = enabled[0] if enabled else None
            if strategy is None:
                self._log(account_id, "ai_decision", "warn",
                          "未找到启用的 AI 策略，本轮跳过", {"accountId": account_id})
                summary["errors"].append("未找到启用的 AI 策略")
                return summary

            params = dict(DEFAULT_STRATEGY_PARAMS)
            if isinstance(strategy.params, dict):
                params.update(strategy.params)
            summary["strategyId"] = strategy.id
            summary["strategyName"] = strategy.name

            universe = self._universe(account_id, params)[: int(params.get("maxScan", 20))]
            summary["watched"] = len(universe)
            max_positions = int(params.get("maxPositions", 5))
            per_trade_pct = float(params.get("perTradePct", 0.15))
            sl_pct = float(params.get("stopLossPct", 0.08))
            tp_pct = float(params.get("takeProfitPct", 0.20))

            # 当前持仓
            positions = self.position_repo.list_positions(account_id)
            held = {p.code: p for p in positions}
            acct = self.account_repo.get_account(account_id)
            available = (acct.cash - acct.frozen_cash) if acct else 0.0

            for code in universe:
                try:
                    sig = self.decide(code, params)
                    summary["dataSource"] = market_provider.quote(code).get("dataSource", "")
                except Exception as e:
                    summary["errors"].append(f"{code} 决策异常: {e}")
                    continue
                # 落信号
                self._save_signal(account_id, sig)
                summary["signals"] += 1

                if sig["signal_type"] == "buy":
                    if code in held and held[code].shares > 0:
                        continue  # 已持有，不重复买入
                    if len([c for c, p in held.items() if p.shares > 0]) >= max_positions:
                        summary["skipped"] += 1
                        continue
                    # 每次买入前刷新可用资金（避免一轮内重复占用）
                    acct = self.account_repo.get_account(account_id)
                    available = (acct.cash - acct.frozen_cash) if acct else 0.0
                    price_now = float(market_provider.quote(code).get("price") or 0.0)
                    qty = self._buy_qty(available, price_now, per_trade_pct)
                    if qty < 100:
                        summary["skipped"] += 1
                        continue
                    try:
                        self._ai_buy(account_id, code, sig, qty, sl_pct, tp_pct)
                        summary["buys"] += 1
                    except PaperError as e:
                        self._log(account_id, "ai_trade", "warn",
                                  f"{code} 买入被拦截：{e.message}", {"code": code, "qty": qty})
                        summary["errors"].append(f"{code}: {e.message}")
                elif sig["signal_type"] == "sell":
                    pos = held.get(code)
                    if pos and pos.shares > 0 and pos.sellable_shares > 0:
                        try:
                            self._ai_sell(account_id, code, pos.sellable_shares, sig)
                            summary["sells"] += 1
                        except PaperError as e:
                            summary["errors"].append(f"{code}: {e.message}")

            # 止损/止盈监控 + AI 持仓 SL/TP 回填
            summary["stopTriggers"] = self.monitor_stops(account_id, params)

            # 写回策略绩效（最近一轮摘要）
            strategy.metrics = {
                "lastRunAt": datetime.utcnow().isoformat(),
                "signals": summary["signals"], "buys": summary["buys"],
                "sells": summary["sells"], "stopTriggers": summary["stopTriggers"],
            }
            with SessionLocal() as db:
                obj = db.get(PaperStrategy, strategy.id)
                if obj:
                    obj.metrics = strategy.metrics
                    obj.updated_at = datetime.utcnow()
                    db.commit()

            self._log(account_id, "ai_decision", "info",
                      f"策略「{strategy.name}」运行完成：信号 {summary['signals']} 笔，"
                      f"买入 {summary['buys']}，卖出 {summary['sells']}，止损止盈触发 {summary['stopTriggers']}",
                      summary)
        except Exception as e:
            summary["errors"].append(f"运行异常: {e}")
            self._log(account_id, "ai_trade", "error", f"AI 自动交易异常：{e}", {"accountId": account_id})
        finally:
            _LAST_RUN[account_id]["running"] = False
            _LAST_RUN[account_id]["at"] = datetime.utcnow().isoformat()
            _LAST_RUN[account_id]["summary"] = {k: summary[k] for k in
                ("signals", "buys", "sells", "stopTriggers", "watched")}
        return summary

    # ——————————————————————— 内部下单 ———————————————————————
    def _buy_qty(self, available: float, price: float, per_trade_pct: float) -> int:
        if price <= 0 or available <= 0:
            return 0
        amount = available * per_trade_pct
        qty = int(amount / price // 100) * 100
        return qty

    def _ai_buy(self, account_id: int, code: str, sig: dict, qty: int,
                sl_pct: float, tp_pct: float):
        price = round(float(market_provider.quote(code).get("price") or 0.0) * 1.01, 2)
        if price <= 0:
            return
        req = CreateOrderRequest(
            accountId=account_id, code=code, name=sig.get("name", ""),
            direction="buy", orderType="ai", price=price, quantity=qty,
            source="ai",
            params={"stopLossPct": sl_pct, "takeProfitPct": tp_pct,
                    "signalStrength": sig.get("strength")},
        )
        res = self.order_svc.create_order(req)
        filled = any(o.status in ("filled", "partial") for o in res)
        if filled:
            self._apply_sltp(account_id, code, sl_pct, tp_pct)
            self._log(account_id, "ai_trade", "info",
                      f"AI 买入 {code} {qty} 股成交，已设止损/止盈", {"code": code, "qty": qty})
        else:
            self._log(account_id, "ai_trade", "info",
                      f"AI 买入 {code} {qty} 股已挂单（待撮合）", {"code": code, "qty": qty})

    def _ai_sell(self, account_id: int, code: str, qty: int, sig: dict):
        price = round(float(market_provider.quote(code).get("price") or 0.0) * 0.99, 2)
        if price <= 0:
            return
        req = CreateOrderRequest(
            accountId=account_id, code=code, name=sig.get("name", ""),
            direction="sell", orderType="ai", price=price, quantity=qty, source="ai",
        )
        self.order_svc.create_order(req)
        self._log(account_id, "ai_trade", "info",
                  f"AI 卖出 {code} {qty} 股已提交", {"code": code, "qty": qty})

    def _apply_sltp(self, account_id: int, code: str, sl_pct: float, tp_pct: float):
        """为指定持仓按成本设置止损/止盈价（仅当两者均为 0 时设置，避免覆盖手动值）。"""
        pos = self.position_repo.get_position(account_id, code)
        if pos is None or pos.shares <= 0:
            return
        if pos.stop_loss_price and pos.take_profit_price:
            return
        cost = pos.cost_price or pos.current_price
        if cost <= 0:
            return
        sl = round(cost * (1 - sl_pct), 2)
        tp = round(cost * (1 + tp_pct), 2)
        try:
            self.position_repo.update(pos.id, stop_loss_price=sl, take_profit_price=tp)
        except Exception as e:  # 不应静默吞掉，便于排查
            self._log(account_id, "ai_trade", "error",
                      f"{code} 回写止损/止盈失败：{e}", {"code": code})

    # ——————————————————————— 止损/止盈监控 ———————————————————————
    def monitor_stops(self, account_id: int, params: Optional[dict] = None) -> int:
        """扫描持仓止损/止盈触发，提交条件单；返回本轮触发下单数。"""
        triggered = 0
        positions = self.position_repo.list_positions(account_id)
        auto_sltp = bool((params or {}).get("autoSLTP", True)) if params else True
        # AI 买入过的标的（用于回填 SL/TP）
        ai_codes = self._ai_bought_codes(account_id) if auto_sltp else set()

        for pos in positions:
            if pos.shares <= 0:
                continue
            price = float(market_provider.quote(pos.code).get("price") or 0.0)
            if price <= 0:
                continue
            # 回填：AI 买入但缺 SL/TP 的持仓
            if auto_sltp and pos.code in ai_codes and not pos.stop_loss_price and not pos.take_profit_price:
                cost = pos.cost_price or price
                sl_pct = float((params or {}).get("stopLossPct", 0.08)) if params else 0.08
                tp_pct = float((params or {}).get("takeProfitPct", 0.20)) if params else 0.20
                self.position_repo.update(
                    pos.id,
                    stop_loss_price=round(cost * (1 - sl_pct), 2),
                    take_profit_price=round(cost * (1 + tp_pct), 2),
                )
                continue

            if pos.stop_loss_price and price <= pos.stop_loss_price:
                if not self._has_open_stop(account_id, pos.code):
                    self._submit_stop(account_id, pos, "stop_loss", pos.stop_loss_price)
                    triggered += 1
            elif pos.take_profit_price and price >= pos.take_profit_price:
                if not self._has_open_stop(account_id, pos.code):
                    self._submit_stop(account_id, pos, "stop_profit", pos.take_profit_price)
                    triggered += 1
        return triggered

    def _submit_stop(self, account_id: int, pos: PaperPosition, otype: str, trigger: float):
        req = CreateOrderRequest(
            accountId=account_id, code=pos.code, name=pos.name,
            direction="sell", orderType=otype, price=round(pos.current_price, 2),
            quantity=max(pos.sellable_shares, 0), triggerPrice=trigger, source="ai",
        )
        try:
            self.order_svc.create_order(req)
            self._log(account_id, "ai_trade", "warn",
                      f"{'止损' if otype=='stop_loss' else '止盈'}触发：{pos.code} "
                      f"现价 {pos.current_price} 触及 {trigger}", {"code": pos.code, "type": otype})
        except PaperError as e:
            self._log(account_id, "ai_trade", "warn",
                      f"{pos.code} 条件单提交失败：{e.message}", {"code": pos.code})

    def _has_open_stop(self, account_id: int, code: str) -> bool:
        open_orders = self.order_repo.list_pending(account_id)
        return any(o.code == code and o.order_type in ("stop_loss", "stop_profit")
                   for o in open_orders)

    def _ai_bought_codes(self, account_id: int) -> set:
        with SessionLocal() as db:
            rows = (
                db.query(PaperOrder.code)
                .filter(PaperOrder.account_id == account_id,
                        PaperOrder.source == "ai",
                        PaperOrder.direction == "buy",
                        PaperOrder.status.in_(["filled", "partial"]))
                .distinct()
                .all()
            )
            return {r[0] for r in rows}

    # ——————————————————————— 信号 / 日志 / 状态 ———————————————————————
    def _save_signal(self, account_id: int, sig: dict):
        s = Signal(
            account_id=account_id, code=sig["code"], name=sig.get("name", ""),
            signal_type=sig["signal_type"], strength=float(sig.get("strength", 0.0)),
            source="ai", reason=sig.get("reason", ""),
            price_target=float(sig.get("price_target", 0.0)),
            stop_loss=float(sig.get("stop_loss", 0.0)),
            take_profit=float(sig.get("take_profit", 0.0)),
            risk_score=float(sig.get("risk_score", 0.0)),
        )
        self.signal_repo.add_signal(s)

    def _log(self, account_id: int, log_type: str, level: str, message: str, meta: dict = None):
        try:
            self.log_repo.add_log(account_id, log_type, level, message, meta or {})
        except Exception:
            pass

    def list_signals(self, account_id: int, limit: int = 50, code: Optional[str] = None) -> List[Signal]:
        return self.signal_repo.list_recent(account_id, limit=limit, code=code)

    def list_ai_logs(self, account_id: int, limit: int = 50) -> List:
        return self.log_repo.list_recent(account_id, limit=limit, log_type=None)

    def auto_status(self, account_id: int) -> dict:
        enabled = self.strategy_repo.enabled_for_account(account_id)
        st = _LAST_RUN.get(account_id, {})
        return {
            "accountId": account_id,
            "enabledStrategies": len(enabled),
            "running": bool(st.get("running", False)),
            "lastRunAt": st.get("at", ""),
            "lastRunSummary": st.get("summary", {}),
            "dataSource": "",
            "watchedCodes": 0,
        }

    def set_holding_sltp(self, account_id: int, code: str,
                         stop_loss_price: float, take_profit_price: float) -> PaperPosition:
        pos = self.position_repo.get_position(account_id, code)
        if pos is None:
            raise PaperError(f"持仓不存在: {code}", "POSITION_NOT_FOUND")
        return self.position_repo.update(
            pos.id, stop_loss_price=stop_loss_price, take_profit_price=take_profit_price)
