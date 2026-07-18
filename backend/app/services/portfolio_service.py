"""组合管理服务 — 模拟账户 + Brinson 归因 + VaR/CVaR + 再平衡建议。

设计要点：
  - 模拟账户初始资金 1,000,000 元，所有交易在 SQLite 持久化
  - Brinson 归因：配置效应 + 选股效应 + 交互效应
  - VaR/CVaR：历史模拟法（滚动窗口 252 日）
  - 再平衡建议：目标权重偏离度 → 调仓方案
  - 实时估值：通过 westock-data quote 获取最新价
"""
from __future__ import annotations

import datetime
import math
import time
from functools import lru_cache
from typing import Optional

import numpy as np

from app.db.database import SessionLocal
from app.db.models import PortfolioPosition, PortfolioOrder, PortfolioSnapshot
from app.services.westock_client import run_table

# ============================================================
# 模拟账户配置
# ============================================================
INITIAL_CAPITAL = 1_000_000.0  # 初始资金 100 万

# 宽基指数 → 行业指数映射（Brinson 基准）
BENCHMARK_INDICES = {
    "000300": "沪深300",
    "000905": "中证500",
}

# 行业 → 基准权重（简化沪深300行业权重）
INDUSTRY_BENCHMARK_WEIGHTS = {
    "食品饮料": 0.15, "银行": 0.12, "非银金融": 0.10,
    "医药生物": 0.09, "电子": 0.09, "电力设备": 0.08,
    "计算机": 0.05, "汽车": 0.05, "基础化工": 0.04,
    "有色金属": 0.04, "国防军工": 0.03, "房地产": 0.03,
    "建筑装饰": 0.02, "交通运输": 0.02, "公用事业": 0.02,
    "其他": 0.07,
}


# ============================================================
# 股价获取
# ============================================================
def _get_live_price(code: str) -> float | None:
    """通过 westock-data quote 获取最新价。"""
    try:
        r = run_table(["quote", code], timeout=10)
        if r:
            d = r[0]
            price = float(d.get("last", d.get("price", 0)))
            if price > 0:
                return price
    except Exception:
        pass
    return None


def _batch_live_prices(codes: list) -> dict:
    """并行获取多只股票实时价，返回 {code: price}。失败/超时的 code 不在结果中。"""
    if not codes:
        return {}
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    with ThreadPoolExecutor(max_workers=min(len(codes), 8)) as ex:
        futures = {ex.submit(_get_live_price, c): c for c in codes}
        for c, f in futures.items():
            try:
                p = f.result()
                if p is not None:
                    out[c] = p
            except Exception:
                pass
    return out


def _get_historical_prices(code: str, days: int = 252) -> list[float]:
    """获取历史收盘价序列（前复权），用于 VaR 计算。"""
    try:
        r = run_table(["kline", code, "--period", "day", "--limit", str(days + 5), "--fq", "qfq"], timeout=15)
        if not r:
            return []
        closes = []
        for row in r:
            c = float(row.get("close", row.get("last", 0)))
            if c > 0:
                closes.append(c)
        return closes[-days:] if len(closes) >= days else closes
    except Exception:
        return []


# ============================================================
# 账户管理
# ============================================================
def _get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def get_account_summary() -> dict:
    """获取账户概览：总资产 / 现金 / 持仓市值 / 当日盈亏。"""
    db = _get_db()
    try:
        positions = db.query(PortfolioPosition).all()
        _prices = _batch_live_prices([p.code for p in positions])
        total_cost = 0.0
        total_market = 0.0
        position_list = []

        for p in positions:
            live = _prices.get(p.code)
            if live is None:
                live = p.current_price or p.avg_cost
            market_value = live * p.shares
            cost_value = p.avg_cost * p.shares
            unrealized = market_value - cost_value
            unrealized_pct = (unrealized / cost_value * 100) if cost_value > 0 else 0

            total_cost += cost_value
            total_market += market_value
            position_list.append({
                "code": p.code,
                "name": p.name,
                "shares": p.shares,
                "avgCost": round(p.avg_cost, 2),
                "currentPrice": round(live, 2),
                "marketValue": round(market_value, 2),
                "costValue": round(cost_value, 2),
                "unrealizedPnl": round(unrealized, 2),
                "unrealizedPnlPct": round(unrealized_pct, 2),
                "weight": round(market_value / max(total_market, 1) * 100, 1),
            })

        # 现金 = 初始资金 - 已投入成本 + 已实现盈亏
        orders = db.query(PortfolioOrder).filter(PortfolioOrder.status == "filled").all()
        cash_flow = 0.0
        for o in orders:
            sign = -1 if o.direction == "buy" else 1
            cash_flow += sign * o.amount

        cash = round(INITIAL_CAPITAL + cash_flow, 2)
        total_value = round(cash + total_market, 2)
        total_return = round((total_value / INITIAL_CAPITAL - 1) * 100, 2)

        # 当日盈亏（从最近一次快照估算）
        last_snap = db.query(PortfolioSnapshot).order_by(
            PortfolioSnapshot.date.desc()
        ).first()
        today_pnl = 0.0
        today_pnl_pct = 0.0
        if last_snap:
            today_pnl = round(total_value - last_snap.total_value, 2)
            today_pnl_pct = round(today_pnl / max(last_snap.total_value, 1) * 100, 2)

        return {
            "totalValue": total_value,
            "cash": cash,
            "positionValue": round(total_market, 2),
            "totalReturn": total_return,
            "totalReturnAmount": round(total_value - INITIAL_CAPITAL, 2),
            "todayPnl": today_pnl,
            "todayPnlPct": today_pnl_pct,
            "initialCapital": INITIAL_CAPITAL,
            "positionCount": len(positions),
        }
    finally:
        db.close()


def get_positions() -> list[dict]:
    """获取当前持仓列表。"""
    summary = get_account_summary()
    db = _get_db()
    try:
        positions = db.query(PortfolioPosition).all()
        _prices = _batch_live_prices([p.code for p in positions])
        result = []
        total_market = 0.0
        for p in positions:
            live = _prices.get(p.code) or p.current_price or p.avg_cost
            market_value = live * p.shares
            total_market += market_value

        for p in positions:
            live = _prices.get(p.code) or p.current_price or p.avg_cost
            market_value = live * p.shares
            cost_value = p.avg_cost * p.shares
            result.append({
                "code": p.code,
                "name": p.name,
                "shares": p.shares,
                "avgCost": round(p.avg_cost, 2),
                "currentPrice": round(live, 2),
                "marketValue": round(market_value, 2),
                "weight": round(market_value / max(total_market, 1) * 100, 1),
                "unrealizedPnl": round(market_value - cost_value, 2),
                "unrealizedPnlPct": round((market_value - cost_value) / max(cost_value, 1) * 100, 2),
            })
        return result
    finally:
        db.close()


# ============================================================
# 下单 & 撤单
# ============================================================
def place_order(code: str, name: str, direction: str, shares: int,
                price: float | None = None, reason: str = "") -> dict:
    """模拟下单：市价单立即成交，限价单记录后需手动确认。

    返回订单详情，若市价单则同时更新持仓。
    """
    db = _get_db()
    try:
        live_price = price or _get_live_price(code)
        if live_price is None:
            return {"error": "无法获取最新价格", "status": "failed"}

        amount = round(live_price * shares, 2)

        # 检查资金
        summary = get_account_summary()
        if direction == "buy" and amount > summary["cash"]:
            return {
                "error": f"可用资金不足（需要 ¥{amount:,.2f}，可用 ¥{summary['cash']:,.2f}）",
                "status": "failed",
            }

        # 创建订单
        order = PortfolioOrder(
            code=code,
            name=name,
            direction=direction,
            price=live_price,
            shares=shares,
            amount=amount,
            status="filled",
            reason=reason,
        )
        db.add(order)
        db.flush()

        # 更新持仓
        position = db.query(PortfolioPosition).filter(
            PortfolioPosition.code == code
        ).first()

        if direction == "buy":
            if position:
                total_cost = position.avg_cost * position.shares + amount
                position.shares += shares
                position.avg_cost = round(total_cost / position.shares, 4)
            else:
                position = PortfolioPosition(
                    code=code,
                    name=name,
                    shares=shares,
                    avg_cost=live_price,
                    current_price=live_price,
                )
                db.add(position)
        else:  # sell
            if not position or position.shares < shares:
                db.rollback()
                return {"error": "持仓不足", "status": "failed"}
            position.shares -= shares
            if position.shares <= 0:
                db.delete(position)

        position.current_price = live_price
        db.commit()

        return {
            "id": order.id,
            "code": code,
            "name": name,
            "direction": direction,
            "price": round(live_price, 2),
            "shares": shares,
            "amount": amount,
            "status": "filled",
            "reason": reason,
            "message": f"{'买入' if direction == 'buy' else '卖出'} {name} {shares}股 @ ¥{live_price:.2f}",
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e), "status": "failed"}
    finally:
        db.close()


def cancel_order(order_id: int) -> dict:
    """撤单（仅限 pending 状态订单）。"""
    db = _get_db()
    try:
        order = db.query(PortfolioOrder).filter(PortfolioOrder.id == order_id).first()
        if not order:
            return {"error": "订单不存在", "status": "failed"}
        if order.status != "pending":
            return {"error": f"订单状态为 {order.status}，无法撤销", "status": "failed"}
        order.status = "cancelled"
        db.commit()
        return {"id": order.id, "status": "cancelled", "message": "订单已撤销"}
    except Exception as e:
        db.rollback()
        return {"error": str(e), "status": "failed"}
    finally:
        db.close()


def get_orders(limit: int = 50) -> list[dict]:
    """获取历史订单列表。"""
    db = _get_db()
    try:
        orders = db.query(PortfolioOrder).order_by(
            PortfolioOrder.created_at.desc()
        ).limit(limit).all()
        return [{
            "id": o.id,
            "code": o.code,
            "name": o.name,
            "direction": o.direction,
            "price": o.price,
            "shares": o.shares,
            "amount": o.amount,
            "status": o.status,
            "reason": o.reason or "",
            "createdAt": o.created_at.isoformat() if o.created_at else "",
        } for o in orders]
    finally:
        db.close()


# ============================================================
# Brinson 归因
# ============================================================
def get_attribution() -> dict:
    """Brinson 收益归因：配置效应 + 选股效应 + 交互效应。

    简化公式（单期）：
      R_portfolio = Σ w_pi × r_pi     （组合实际收益）
      R_benchmark = Σ w_bi × r_bi     （基准收益）
      Allocation   = Σ (w_pi - w_bi) × r_bi    （配置效应）
      Selection    = Σ w_bi × (r_pi - r_bi)    （选股效应）
      Interaction  = Σ (w_pi - w_bi) × (r_pi - r_bi)  （交互效应）
      Total Excess = Allocation + Selection + Interaction
    """
    positions = get_positions()
    if not positions:
        return {
            "portfolioReturn": 0, "benchmarkReturn": 0,
            "excessReturn": 0, "allocation": 0, "selection": 0,
            "interaction": 0, "breakdown": [],
        }

    # 获取每只股票的行业和近期收益
    total_market = sum(p["marketValue"] for p in positions)
    stock_data = []
    for p in positions:
        code = p["code"]
        # 获取profile取行业
        industry = "其他"
        try:
            r = run_table(["profile", code], timeout=8)
            if r:
                industry = r[0].get("industry", r[0].get("industry_name", "其他"))
        except Exception:
            pass

        # 获取 20 日收益作为本期收益代理
        ret_20d = 0.0
        prices = _get_historical_prices(code, 22)
        if len(prices) >= 21:
            ret_20d = (prices[-1] / prices[-21] - 1) * 100

        stock_data.append({
            "code": p["code"],
            "name": p["name"],
            "weight": p["weight"],
            "return": round(ret_20d, 2),
            "industry": industry,
        })

    # 按行业聚合
    industry_weights = {}
    industry_returns = {}
    for s in stock_data:
        ind = s["industry"]
        industry_weights[ind] = industry_weights.get(ind, 0) + s["weight"]
        if ind not in industry_returns:
            industry_returns[ind] = []
        industry_returns[ind].append(s["return"])

    # 行业收益率 = 该行业内所有持仓等权平均
    industry_avg_return = {}
    for ind, rets in industry_returns.items():
        industry_avg_return[ind] = sum(rets) / len(rets) if rets else 0

    # Brinson 归因
    total_allocation = 0.0
    total_selection = 0.0
    total_interaction = 0.0
    breakdown = []

    for s in stock_data:
        ind = s["industry"]
        w_p = s["weight"] / 100  # 组合内权重
        w_b = INDUSTRY_BENCHMARK_WEIGHTS.get(ind, 0.03)  # 基准权重
        r_p = s["return"]  # 个股收益
        r_b = industry_avg_return.get(ind, 0)  # 行业基准收益

        alloc = (w_p - w_b) * r_b
        sel = w_b * (r_p - r_b)
        inter = (w_p - w_b) * (r_p - r_b)

        total_allocation += alloc
        total_selection += sel
        total_interaction += inter

        breakdown.append({
            "code": s["code"],
            "name": s["name"],
            "industry": ind,
            "portfolioWeight": round(w_p * 100, 1),
            "benchmarkWeight": round(w_b * 100, 1),
            "stockReturn": r_p,
            "industryReturn": round(r_b, 2),
            "allocationEffect": round(alloc, 3),
            "selectionEffect": round(sel, 3),
            "interactionEffect": round(inter, 3),
        })

    # 组合收益和基准收益
    portfolio_return = sum(s["weight"] / 100 * s["return"] for s in stock_data)
    benchmark_return = sum(
        w * industry_avg_return.get(ind, 0)
        for ind, w in INDUSTRY_BENCHMARK_WEIGHTS.items()
    )

    return {
        "portfolioReturn": round(portfolio_return, 3),
        "benchmarkReturn": round(benchmark_return, 3),
        "excessReturn": round(portfolio_return - benchmark_return, 3),
        "allocation": round(total_allocation, 3),
        "selection": round(total_selection, 3),
        "interaction": round(total_interaction, 3),
        "breakdown": breakdown,
    }


# ============================================================
# 风险指标：VaR / CVaR / 波动率 / 夏普
# ============================================================
def get_risk_metrics(confidence: float = 0.95) -> dict:
    """计算组合风险指标。

    方法：历史模拟法 VaR/CVaR
      - 取每只持仓过去 252 个交易日收益率序列
      - 按当前权重合成组合历史收益率
      - 取指定置信水平分位数
    """
    positions = get_positions()
    if not positions:
        return {
            "var95": 0, "cvar95": 0, "var99": 0,
            "annualVolatility": 0, "sharpeRatio": 0, "maxDrawdown": 0,
            "method": "历史模拟法",
        }

    total_market = sum(p["marketValue"] for p in positions)
    weights = []
    all_returns = []

    for p in positions:
        w = p["marketValue"] / total_market
        weights.append(w)
        prices = _get_historical_prices(p["code"], 253)
        if len(prices) >= 253:
            rets = np.diff(prices) / prices[:-1]
        elif len(prices) >= 21:
            rets = np.diff(prices) / prices[:-1]
        else:
            rets = np.zeros(252)
        # 补齐到252
        if len(rets) < 252:
            rets = np.pad(rets, (252 - len(rets), 0), mode="constant")
        all_returns.append(rets[:252])

    # 合成组合收益率
    weights = np.array(weights)
    all_returns = np.array(all_returns)
    portfolio_returns = np.dot(weights, all_returns)

    # VaR / CVaR
    var_95 = np.percentile(portfolio_returns, (1 - 0.95) * 100) * 100
    var_99 = np.percentile(portfolio_returns, (1 - 0.99) * 100) * 100
    cvar_95 = portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)].mean() * 100

    # 年化波动率
    annual_vol = np.std(portfolio_returns) * np.sqrt(252) * 100

    # 夏普比率（无风险利率 2%）
    excess = portfolio_returns.mean() * 252 - 0.02
    sharpe = excess / (np.std(portfolio_returns) * np.sqrt(252)) if np.std(portfolio_returns) > 0 else 0

    # 最大回撤
    cumulative = np.cumprod(1 + portfolio_returns)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - peak) / peak
    max_dd = drawdown.min() * 100

    return {
        "var95": round(abs(var_95), 3),
        "cvar95": round(abs(cvar_95), 3),
        "var99": round(abs(var_99), 3),
        "annualVolatility": round(annual_vol, 2),
        "sharpeRatio": round(sharpe, 2),
        "maxDrawdown": round(abs(max_dd), 2),
        "method": "历史模拟法（252日滚动窗口）",
        "confidence": f"{confidence:.0%}",
    }


# ============================================================
# 再平衡建议
# ============================================================
DEFAULT_TARGET_WEIGHTS = {
    "食品饮料": 15, "银行": 12, "非银金融": 10,
    "医药生物": 9, "电子": 9, "电力设备": 8,
    "计算机": 5, "汽车": 5, "基础化工": 4,
    "有色金属": 4, "其他": 19,
}


def get_rebalance_advice(target_weights: dict | None = None) -> dict:
    """再平衡建议：计算当前权重 vs 目标权重偏离度，生成调仓方案。

    参数：
      target_weights: 目标行业权重 { "食品饮料": 15, ... }，默认使用沪深300近似权重
    """
    if target_weights is None:
        target_weights = DEFAULT_TARGET_WEIGHTS

    positions = get_positions()
    summary = get_account_summary()
    total_value = summary["totalValue"]

    if not positions or total_value <= 0:
        return {"advice": [], "summary": "无持仓数据", "totalValue": total_value}

    # 获取每只股票行业
    stock_info = []
    for p in positions:
        industry = "其他"
        try:
            r = run_table(["profile", p["code"]], timeout=8)
            if r:
                industry = r[0].get("industry", r[0].get("industry_name", "其他"))
        except Exception:
            pass
        stock_info.append({**p, "industry": industry})

    # 当前行业权重
    current_industry = {}
    for s in stock_info:
        ind = s["industry"]
        current_industry[ind] = current_industry.get(ind, 0) + s["marketValue"]

    # 行业偏离度 + 调仓建议
    advice_items = []
    for ind, target_pct in target_weights.items():
        current_mv = current_industry.get(ind, 0)
        current_pct = (current_mv / total_value * 100) if total_value > 0 else 0
        target_mv = total_value * target_pct / 100
        diff_mv = target_mv - current_mv
        diff_pct = target_pct - current_pct

        if abs(diff_pct) > 2:  # 偏离 > 2% 才建议
            advice_items.append({
                "industry": ind,
                "currentWeight": round(current_pct, 1),
                "targetWeight": target_pct,
                "drift": round(diff_pct, 1),
                "adjustAmount": round(diff_mv, 2),
                "action": "增配" if diff_mv > 0 else "减配",
                "severity": "high" if abs(diff_pct) > 8 else ("medium" if abs(diff_pct) > 4 else "low"),
            })

    # 排序：偏离大的优先
    advice_items.sort(key=lambda x: abs(x["drift"]), reverse=True)

    return {
        "totalValue": total_value,
        "advice": advice_items,
        "summary": f"共 {len(advice_items)} 个行业需要调仓" if advice_items else "当前配置已接近目标，无需调仓",
        "targetWeights": target_weights,
        "currentIndustryWeights": {
            ind: round(mv / total_value * 100, 1)
            for ind, mv in sorted(current_industry.items(), key=lambda x: -x[1])
        },
    }


# ============================================================
# 快照管理
# ============================================================
def take_snapshot() -> dict:
    """保存当前组合快照。"""
    db = _get_db()
    try:
        summary = get_account_summary()
        positions = get_positions()
        risk = get_risk_metrics()

        snap = PortfolioSnapshot(
            date=datetime.date.today(),
            total_value=summary["totalValue"],
            cash=summary["cash"],
            position_value=summary["positionValue"],
            daily_pnl=summary["todayPnl"],
            daily_pnl_pct=summary["todayPnlPct"],
            cumulative_pnl=summary["totalReturnAmount"],
            cumulative_pnl_pct=summary["totalReturn"],
            positions=positions,
            metrics=risk,
        )
        db.add(snap)
        db.commit()
        return {"status": "ok", "date": str(datetime.date.today())}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def get_snapshot_history(days: int = 30) -> list[dict]:
    """获取历史快照序列。"""
    db = _get_db()
    try:
        snaps = db.query(PortfolioSnapshot).order_by(
            PortfolioSnapshot.date.asc()
        ).limit(days).all()
        return [{
            "date": str(s.date),
            "totalValue": s.total_value,
            "cash": s.cash,
            "positionValue": s.position_value,
            "dailyPnl": s.daily_pnl,
            "dailyPnlPct": s.daily_pnl_pct,
            "cumulativePnl": s.cumulative_pnl,
            "cumulativePnlPct": s.cumulative_pnl_pct,
        } for s in snaps]
    finally:
        db.close()


# ============================================================
# 组合全量数据（供 Dashboard V2 调用）
# ============================================================
def get_portfolio_full() -> dict:
    """组合全量数据：概览 + 持仓 + 风险指标。"""
    overview = get_account_summary()
    positions = get_positions()
    risk = get_risk_metrics()
    return {
        "overview": overview,
        "positions": positions,
        "risk": risk,
    }
