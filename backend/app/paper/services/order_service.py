"""模拟盘交易系统 — 订单服务与撮合引擎（Service Layer）。

这是 M3 的核心。负责：
- 订单创建（限价 / 市价 / 止盈 / 止损 / 分批建仓减仓 / 网格 / AI 自动单）；
- 订单状态机（pending → partial → filled；pending → cancelled / expired）；
- 撮合引擎：依据 A股规则（trading_rules）对接实时行情（market_provider）撮合成交；
- 成交后原子更新：账户现金/冻结、持仓（position_service）、成交记录；
- 后台重试：对挂单按行情轮询撮合（retry_pending_orders）。

撮合建模说明（诚实简化，详见交付说明）：
- 市价单按当前最新价成交（含价格改进：限价买按 min(委托价, 市价)）；
- 限价单价格条件满足即全部/部分成交，否则保持挂单；
- 止盈/止损为卖出条件单，触发价触及后按市价卖出；
- 分批/网格通过「父订单 + 子订单」实现（parent_id 关联）。
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.paper.domain_models import PaperAccount, PaperOrder, PaperTrade, PaperPosition
from app.paper.services.order_repo import OrderRepository
from app.paper.repositories.account_repo import AccountRepository
from app.paper.services.position_service import PositionService
from app.paper.services.risk_service import RiskService
from app.paper.services.market_provider import market_provider
from app.paper.schemas import (
    CreateOrderRequest,
    OrderResponse,
    PositionResponse,
)
from app.paper import trading_rules as R
from app.paper.errors import PaperError
from app.paper.metrics import ORDER_COUNTER, MATCH_LATENCY, PENDING_ORDERS

_BATCH_MAX = 20          # 分批最大笔数
_GRID_MAX_CHILDREN = 40  # 网格最大子单数量


class OrderService:
    def __init__(self):
        self.order_repo = OrderRepository()
        self.account_repo = AccountRepository()
        self.position_svc = PositionService()
        self.risk_svc = RiskService()          # M5 前置风控

    # ============================================================
    # 订单创建
    # ============================================================
    def create_order(self, req: CreateOrderRequest) -> List[OrderResponse]:
        """创建订单。单笔返回 [OrderResponse]，分批/网格返回多笔。"""
        # 基础校验
        if req.direction not in ("buy", "sell"):
            raise PaperError("direction 必须为 buy 或 sell", "INVALID_DIRECTION")
        if req.orderType not in ("limit", "market", "stop_profit", "stop_loss", "grid", "ai"):
            raise PaperError(f"不支持的订单类型: {req.orderType}", "INVALID_ORDER_TYPE")
        if not R.validate_lot(req.quantity):
            raise PaperError("数量必须为 100 股的整数倍", "INVALID_LOT")

        # 网格 / 分批走专用构造
        if req.orderType == "grid":
            return self._create_grid(req)
        if req.tranches and req.tranches > 1:
            return self._create_batch(req)

        # M5 前置风控 + A 股特有规则（#P0）：涨跌停/自成交检测
        if req.direction == "buy":
            ok, vios = self.risk_svc.evaluate_pre_trade(
                req.accountId, req.code, "buy",
                req.orderType if req.orderType != "market" else "limit",
                req.price or 0.0, req.quantity)
            if not ok:
                self.risk_svc.record_event(
                    req.accountId, req.code, "ORDER_BLOCKED", "high",
                    "；".join(vios), {"direction": "buy", "orderType": req.orderType,
                                      "price": req.price, "quantity": req.quantity, "violations": vios})
                raise PaperError("；".join(vios), "RISK_BLOCKED")

        order = self._place_single(
            account_id=req.accountId, code=req.code, name=req.name or "",
            direction=req.direction, order_type=req.orderType,
            price=req.price or 0.0, quantity=req.quantity,
            trigger_price=req.triggerPrice or 0.0, source=req.source or "human",
            parent_id=0, remark=req.remark or "",
        )
        return [self._to_response(order)]

    # —— 分批建仓 / 减仓 ——
    def _create_batch(self, req: CreateOrderRequest) -> List[OrderResponse]:
        tranches = min(max(2, int(req.tranches)), _BATCH_MAX)
        per = (req.quantity // tranches // R.LOT_SIZE) * R.LOT_SIZE
        if per < R.LOT_SIZE:
            per = R.LOT_SIZE
        parent_id = 0
        out: List[PaperOrder] = []
        # M5 前置风控：分批为同一笔买入意图，按总量一次性校验集中度/总仓位/单日亏损
        if req.direction == "buy":
            ok, vios = self.risk_svc.evaluate_pre_trade(
                req.accountId, req.code, "buy",
                req.orderType if req.orderType != "market" else "limit",
                req.price or 0.0, req.quantity)
            if not ok:
                self.risk_svc.record_event(
                    req.accountId, req.code, "ORDER_BLOCKED", "high",
                    "；".join(vios), {"direction": "buy", "orderType": req.orderType,
                                      "price": req.price, "quantity": req.quantity, "violations": vios})
                raise PaperError("；".join(vios), "RISK_BLOCKED")
        for i in range(tranches):
            # 最后一笔补齐余数，保证总量一致
            qty = per if i < tranches - 1 else (req.quantity - per * (tranches - 1))
            if qty <= 0:
                continue
            order = self._place_single(
                account_id=req.accountId, code=req.code, name=req.name or "",
                direction=req.direction, order_type=req.orderType if req.orderType != "market" else "limit",
                price=req.price or 0.0, quantity=qty,
                trigger_price=req.triggerPrice or 0.0, source=req.source or "human",
                parent_id=parent_id, remark=f"分批 {i+1}/{tranches}",
                skip_risk=True,
            )
            if parent_id == 0:
                parent_id = order.id
                # 回填父 id
                with SessionLocal() as db:
                    o = db.get(PaperOrder, order.id)
                    if o:
                        o.parent_id = order.id
                        db.commit()
                self._set_parent(order.id, order.id)
            out.append(order)
        return [self._to_response(o) for o in out]

    def _set_parent(self, order_id: int, parent_id: int):
        with SessionLocal() as db:
            o = db.get(PaperOrder, order_id)
            if o:
                o.parent_id = parent_id
                db.commit()

    # —— 网格 ——
    def _create_grid(self, req: CreateOrderRequest) -> List[OrderResponse]:
        upper = req.gridUpper or 0.0
        lower = req.gridLower or 0.0
        step = req.gridStep or 0.0
        qty_per = req.gridQtyPer or R.LOT_SIZE
        if upper <= lower or step <= 0 or qty_per < R.LOT_SIZE or qty_per % R.LOT_SIZE != 0:
            raise PaperError("网格参数非法（需 upper>lower, step>0, qtyPer 为整手）", "GRID_PARAM")
        # 取当前价作为中枢
        quote = market_provider.quote(req.code)
        center = quote.get("price") or (lower + upper) / 2
        levels = []
        p = lower
        while p <= upper + 1e-9 and len(levels) < _GRID_MAX_CHILDREN:
            levels.append(round(p, 2))
            p += step
        parent_id = 0
        out: List[PaperOrder] = []
        # M5 前置风控：网格为中性策略，对买入侧总量做一次聚合校验（避免单格误伤）
        buy_notional = sum(lvl * qty_per for lvl in levels if lvl < center)
        if buy_notional > 0:
            ok, vios = self.risk_svc.evaluate_pre_trade(
                req.accountId, req.code, "buy", "limit", center, qty_per)
            if not ok:
                self.risk_svc.record_event(
                    req.accountId, req.code, "ORDER_BLOCKED", "high",
                    "；".join(vios), {"strategy": "grid", "violations": vios})
                raise PaperError("；".join(vios), "RISK_BLOCKED")
        for lvl in levels:
            # 低于中枢挂买，高于中枢挂卖
            if lvl < center:
                direction = "buy"
            elif lvl > center:
                direction = "sell"
            else:
                continue
            order = self._place_single(
                account_id=req.accountId, code=req.code, name=req.name or "",
                direction=direction, order_type="limit",
                price=lvl, quantity=qty_per, trigger_price=0.0,
                source=req.source or "human", parent_id=parent_id,
                remark=f"网格 {lvl}", skip_limit=True, skip_risk=True,
            )
            if parent_id == 0:
                parent_id = order.id
                self._set_parent(order.id, order.id)
            out.append(order)
        if not out:
            raise PaperError("网格未生成任何子单", "GRID_EMPTY")
        return [self._to_response(o) for o in out]

    # —— 单笔下单 + 即时撮合 ——
    def _place_single(self, *, account_id: int, code: str, name: str, direction: str,
                      order_type: str, price: float, quantity: int, trigger_price: float,
                      source: str, parent_id: int, remark: str,
                      skip_limit: bool = False, skip_risk: bool = False) -> PaperOrder:
        with SessionLocal() as db:
            acct = db.get(PaperAccount, account_id)
            if not acct:
                raise PaperError(f"账户不存在: {account_id}", "ACCOUNT_NOT_FOUND")

            # 交易时间校验：市价单需实时盘口，非交易时段拒绝；
            # 限价/止盈止损/网格/分批为挂单，允许盘前/盘后提交（次日或触发后成交）。
            if order_type == "market" and not R.is_trading_time():
                raise PaperError("当前为非交易时段，市价单无法提交（挂单请用限价/条件单）", "NOT_TRADING_TIME")

            # 涨跌停校验（限价单需在区间内；网格子单放宽，越界单仅不成交）
            quote = market_provider.quote(code)
            prev_close = quote.get("prevClose") or 0.0
            is_st = (name or quote.get("name") or "").startswith(("ST", "*ST"))
            if order_type in ("limit",) and price > 0 and prev_close > 0 and not skip_limit:
                if not R.validate_price_in_limit(code, price, prev_close, is_st):
                    low, high = R.price_limit(code, prev_close, is_st)
                    raise PaperError(
                        f"委托价 {price} 超出涨跌停区间 [{low}, {high}]", "PRICE_LIMIT")

            # M5 前置风控：买入方向校验集中度/总仓位/单笔金额/单日亏损
            if not skip_risk:
                ok, vios = self.risk_svc.evaluate_pre_trade(
                    account_id, code, direction, order_type, price, quantity)
                if not ok:
                    # 拦截并落库风险事件
                    self.risk_svc.record_event(
                        account_id, code, "ORDER_BLOCKED", "high",
                        "；".join(vios), {"direction": direction, "orderType": order_type,
                                          "price": price, "quantity": quantity, "violations": vios})
                    from app.paper.metrics import RISK_BLOCKED
                    RISK_BLOCKED.labels(rule_type="pre_trade").inc()
                    raise PaperError("；".join(vios), "RISK_BLOCKED")

            # 资源预检 + 冻结
            if direction == "buy":
                if order_type == "limit":
                    est_amt = price * quantity
                    est_fee = R.estimate_fee("buy", est_amt)
                    need = est_amt + est_fee
                    available = acct.cash - acct.frozen_cash
                    if need > available + 1e-6:
                        raise PaperError(
                            f"可用资金不足：需 {need:.2f}，可用 {available:.2f}", "INSUFFICIENT_CASH")
                    acct.frozen_cash = round(acct.frozen_cash + need, 2)
                    acct.available_cash = round(acct.cash - acct.frozen_cash, 2)
            else:  # sell
                avail = self._available_sellable(db, account_id, code)
                if avail < quantity:
                    raise PaperError(
                        f"可卖数量不足：可卖 {avail}，委托 {quantity}", "INSUFFICIENT_SHARES")
                # 注：不在持仓上预减可卖，成交时再减，避免重复扣减

            order = PaperOrder(
                account_id=account_id, code=code, name=name or quote.get("name", ""),
                direction=direction, order_type=order_type, price=price,
                quantity=quantity, filled_quantity=0, avg_fill_price=0.0,
                amount=0.0, fee=0.0, status="pending", source=source,
                parent_id=parent_id, trigger_price=trigger_price, remark=remark,
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            ORDER_COUNTER.labels(direction=direction, status="pending").inc()
            oid = order.id

        # 下单后即时尝试撮合（市价/限价/已触发条件单）
        return self._match_one(oid)

    # ============================================================
    # 撮合引擎
    # ============================================================
    def _match_one(self, order_id: int) -> PaperOrder:
        # 交易时段检查（#P0）：非连续竞价时段不撮合
        from app.paper.trading_session import TradingSession
        if not TradingSession.can_match():
            with SessionLocal() as db:
                return db.get(PaperOrder, order_id)

        with SessionLocal() as db:
            order = db.get(PaperOrder, order_id)
            if order is None or order.status not in ("pending", "partial"):
                return order
            return self._attempt_fill(db, order)

    def _attempt_fill(self, db: Session, order: PaperOrder) -> PaperOrder:
        acct = db.get(PaperAccount, order.account_id)
        quote = market_provider.quote(order.code)
        if not quote or not quote.get("price"):
            return order  # 无行情，保持挂单

        market_price = float(quote["price"])
        prev_close = float(quote.get("prevClose") or 0.0)
        is_st = (order.name or quote.get("name") or "").startswith(("ST", "*ST"))
        remaining = order.quantity - order.filled_quantity

        # —— 判定是否可成交及成交价 ——
        fill_price = 0.0
        actionable = False
        if order.order_type == "market":
            fill_price = market_price
            actionable = True
        elif order.order_type in ("limit", "ai"):
            if order.direction == "buy":
                if market_price <= order.price + 1e-9:
                    fill_price = min(order.price, market_price)  # 价格改进
                    actionable = True
            else:
                if market_price >= order.price - 1e-9:
                    fill_price = max(order.price, market_price)
                    actionable = True
        elif order.order_type in ("stop_profit", "stop_loss"):
            # 条件单：止盈=价格升至触发价卖出；止损=价格跌至触发价卖出
            tp = order.trigger_price
            if tp > 0:
                if order.order_type == "stop_profit" and market_price >= tp - 1e-9:
                    fill_price = market_price
                    actionable = True
                elif order.order_type == "stop_loss" and market_price <= tp + 1e-9:
                    fill_price = market_price
                    actionable = True

        if not actionable or fill_price <= 0:
            return order

        # —— 资源约束 → 成交数量 ——
        qty = remaining
        if order.direction == "buy":
            available_cash = acct.cash - acct.frozen_cash
            affordable = R.max_affordable_shares(available_cash, fill_price)
            qty = min(qty, affordable)
            if qty < R.LOT_SIZE:
                return order  # 资金不足，保持挂单（限价）/ 市价则下方按部分成交处理
            amount = fill_price * qty
            fee = R.estimate_fee("buy", amount)
            if amount + fee > available_cash + 1e-6:
                qty = R.max_affordable_shares(available_cash, fill_price)
                if qty < R.LOT_SIZE:
                    return order
                amount = fill_price * qty
                fee = R.estimate_fee("buy", amount)
            # 现金扣减
            acct.cash = round(acct.cash - (amount + fee), 2)
            if order.order_type == "limit":
                acct.frozen_cash = round(max(0.0, acct.frozen_cash - self._frozen_for(order, qty)), 2)
            acct.available_cash = round(acct.cash - acct.frozen_cash, 2)
            # 持仓更新
            self.position_svc.apply_buy_fill(
                db, order.account_id, order.code, order.name, "", qty, fill_price, fee,
                datetime.now())
            realized = 0.0
        else:  # sell
            avail = self._available_sellable(db, order.account_id, order.code, order.id)
            qty = min(qty, avail)
            if qty < R.LOT_SIZE:
                return order
            amount = fill_price * qty
            fee = R.estimate_fee("sell", amount)
            acct.cash = round(acct.cash + (amount - fee), 2)
            acct.available_cash = round(acct.cash - acct.frozen_cash, 2)
            _, realized = self.position_svc.apply_sell_fill(
                db, order.account_id, order.code, qty, fill_price, fee, datetime.now())

        # —— 成交记录 ——
        trade = PaperTrade(
            account_id=order.account_id, order_id=order.id, code=order.code,
            name=order.name, direction=order.direction, price=fill_price,
            quantity=qty, amount=round(amount, 2), fee=fee,
            realized_pnl=realized, trade_time=datetime.now(),
        )
        db.add(trade)
        # —— 订单状态推进 ——
        order.filled_quantity += qty
        order.avg_fill_price = round(
            (order.avg_fill_price * (order.filled_quantity - qty) + fill_price * qty)
            / order.filled_quantity, 4) if order.filled_quantity else fill_price
        order.amount = round(order.amount + amount, 2)
        order.fee = round(order.fee + fee, 2)
        if order.filled_quantity >= order.quantity:
            order.status = "filled"
        else:
            order.status = "partial"
            # 市价单无法继续成交则失效
            if order.order_type == "market":
                order.status = "expired"
        db.commit()
        db.refresh(order)
        return order

    # ============================================================
    # 撤单
    # ============================================================
    def cancel_order(self, account_id: int, order_id: int) -> OrderResponse:
        # 收盘集合竞价期间不接受撤单（#P0）
        from app.paper.trading_session import TradingSession
        if not TradingSession.can_cancel():
            raise PaperError("收盘集合竞价期间不可撤单", "CANCEL_NOT_ALLOWED")

        with SessionLocal() as db:
            order = db.get(PaperOrder, order_id)
            if not order or order.account_id != account_id:
                raise PaperError(f"订单不存在: {order_id}", "ORDER_NOT_FOUND")
            if order.status not in ("pending", "partial"):
                raise PaperError(f"订单状态为 {order.status}，不可撤单", "ORDER_NOT_CANCELABLE")
            acct = db.get(PaperAccount, account_id)
            # 释放冻结
            if order.direction == "buy" and order.order_type == "limit":
                acct.frozen_cash = round(max(0.0, acct.frozen_cash - self._frozen_for(order, order.quantity - order.filled_quantity)), 2)
                acct.available_cash = round(acct.cash - acct.frozen_cash, 2)
            order.status = "cancelled"
            db.commit()
            db.refresh(order)
            ORDER_COUNTER.labels(direction=order.direction, status="cancelled").inc()
            return self._to_response(order)

    # ============================================================
    # 后台重试撮合（挂单轮询）
    # ============================================================
    def retry_pending_orders(self, account_id: Optional[int] = None) -> int:
        """尝试撮合所有 pending/partial 订单，返回本次成交的订单数。"""
        # 非连续竞价时段跳过撮合（#P0）
        from app.paper.trading_session import TradingSession
        if not TradingSession.can_match():
            return 0

        orders = self.order_repo.list_pending(account_id)
        filled = 0
        for o in orders:
            before = o.status
            try:
                res = self._match_one(o.id)
            except Exception:
                continue
            if res is not None and before != res.status and res.status in ("filled", "partial"):
                filled += 1
        return filled

    # ============================================================
    # 查询
    # ============================================================
    def list_orders(self, account_id: int, status: Optional[str] = None) -> List[OrderResponse]:
        orders = self.order_repo.list_orders(account_id, status)
        return [self._to_response(o) for o in orders]

    def get_order(self, account_id: int, order_id: int) -> OrderResponse:
        with SessionLocal() as db:
            o = db.get(PaperOrder, order_id)
            if not o or o.account_id != account_id:
                raise PaperError(f"订单不存在: {order_id}", "ORDER_NOT_FOUND")
            return self._to_response(o)

    def list_positions(self, account_id: int) -> List[PositionResponse]:
        return self.position_svc.list_positions(account_id)

    # ============================================================
    # 内部工具
    # ============================================================
    def _available_sellable(self, db: Session, account_id: int, code: str,
                             exclude_order_id: int = None) -> int:
        """可卖数量 = 持仓可卖 - 该标的挂卖单已冻结量（T+1 + 防重复卖出）。

        exclude_order_id：撮合当前订单时排除其自身（否则会把自己算作冻结）。
        """
        pos = (
            db.query(PaperPosition)
            .filter(PaperPosition.account_id == account_id, PaperPosition.code == code)
            .first()
        )
        if pos is None:
            return 0
        q = (
            db.query(PaperOrder)
            .filter(PaperOrder.account_id == account_id, PaperOrder.code == code,
                    PaperOrder.direction == "sell", PaperOrder.status.in_(["pending", "partial"]))
        )
        if exclude_order_id is not None:
            q = q.filter(PaperOrder.id != exclude_order_id)
        frozen = q.all()
        frozen_qty = sum(o.quantity - o.filled_quantity for o in frozen)
        return max(0, pos.sellable_shares - frozen_qty)

    def _frozen_for(self, order: PaperOrder, filled_qty: int) -> float:
        """该订单因本次成交而应释放的冻结资金。"""
        if order.order_type != "limit" or order.direction != "buy":
            return 0.0
        amt = order.price * filled_qty
        return amt + R.estimate_fee("buy", amt)

    def _to_response(self, o: PaperOrder) -> OrderResponse:
        return OrderResponse(
            id=o.id, accountId=o.account_id, code=o.code, name=o.name,
            direction=o.direction, orderType=o.order_type, price=o.price,
            quantity=o.quantity, filledQuantity=o.filled_quantity,
            avgFillPrice=o.avg_fill_price, amount=o.amount, fee=o.fee,
            status=o.status, source=o.source, triggerPrice=o.trigger_price,
            parentId=o.parent_id, createdAt=o.created_at.isoformat() if o.created_at else "",
            updatedAt=o.updated_at.isoformat() if o.updated_at else "",
        )
