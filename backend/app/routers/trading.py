"""Trading API - 交易系统"""
from fastapi import APIRouter
from app.models.schemas import TradeOrder

router = APIRouter()

# Mock orders
ORDERS = [
    {"id": "ORD001", "time": "14:32:15", "code": "600519", "name": "贵州茅台", "action": "buy", "price": 1742.56, "shares": 100, "status": "filled", "amount": 174256},
    {"id": "ORD002", "time": "14:28:03", "code": "300750", "name": "宁德时代", "action": "sell", "price": 198.34, "shares": 200, "status": "filled", "amount": 39668},
    {"id": "ORD003", "time": "14:15:42", "code": "002594", "name": "比亚迪", "action": "buy", "price": 248.90, "shares": 300, "status": "filled", "amount": 74670},
    {"id": "ORD004", "time": "13:55:18", "code": "601318", "name": "中国平安", "action": "buy", "price": 48.76, "shares": 500, "status": "pending", "amount": 24380},
    {"id": "ORD005", "time": "11:02:33", "code": "000858", "name": "五粮液", "action": "sell", "price": 156.30, "shares": 300, "status": "cancelled", "amount": 46890},
]

RISK_CONFIG = {
    "maxPosition": 25,
    "dailyLossLimit": 5,
    "maxDrawdownLimit": 15,
    "stopLoss": 8,
    "takeProfit": 20,
}


@router.get("/orders")
def list_orders():
    """获取委托记录"""
    return ORDERS


@router.post("/order")
def place_order(order: TradeOrder):
    """提交订单 (MVP: 模拟成交)"""
    return {
        "id": f"ORD{len(ORDERS) + 1:03d}",
        "code": order.code,
        "action": order.action,
        "price": order.price,
        "shares": order.shares,
        "amount": order.price * order.shares,
        "status": "filled",
        "message": f"订单已{'买入' if order.action == 'buy' else '卖出'}成交",
    }


@router.get("/risk-config")
def get_risk_config():
    """获取风控配置"""
    return RISK_CONFIG


@router.get("/stats")
def get_trading_stats():
    """获取今日交易统计"""
    return {
        "totalOrders": 12,
        "filled": 10,
        "pending": 1,
        "cancelled": 1,
        "todayPnl": 32580.32,
    }
