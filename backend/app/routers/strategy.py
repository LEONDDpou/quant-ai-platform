"""Strategy API - 策略管理"""
from fastapi import APIRouter, HTTPException
from app.services.mock_data import STRATEGIES
from app.models.schemas import StrategyCreate

router = APIRouter()


@router.get("/")
def list_strategies():
    """获取策略列表"""
    return [{
        "id": s["id"], "name": s["name"], "type": s["type"], "status": s["status"],
        "annualizedReturn": s["annualizedReturn"], "sharpeRatio": s["sharpeRatio"],
        "maxDrawdown": s["maxDrawdown"], "winRate": s["winRate"],
        "totalTrades": s["totalTrades"], "description": s["description"],
        "equityCurve": s["equityCurve"], "createdAt": s["createdAt"],
    } for s in STRATEGIES]


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str):
    """获取策略详情"""
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            return s
    raise HTTPException(status_code=404, detail="Strategy not found")


@router.post("/")
def create_strategy(config: StrategyCreate):
    """创建新策略 (MVP: 返回模拟结果)"""
    return {
        "id": f"strat-{len(STRATEGIES) + 1:03d}",
        "name": config.name,
        "type": config.type,
        "status": "stopped",
        "stockPool": config.stockPool,
        "description": config.description,
        "message": "策略已创建，请进行回测验证",
    }


@router.post("/{strategy_id}/toggle")
def toggle_strategy(strategy_id: str):
    """启动/停止策略"""
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            s["status"] = "stopped" if s["status"] == "running" else "running"
            new_status = "运行中" if s["status"] == "running" else "已停止"
            return {"id": s["id"], "status": s["status"], "message": f"策略{new_status}"}
    raise HTTPException(status_code=404, detail="Strategy not found")


@router.post("/{strategy_id}/archive")
def archive_strategy(strategy_id: str):
    """归档策略"""
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            s["status"] = "archived"
            return {"id": s["id"], "status": s["status"], "message": "策略已归档"}
    raise HTTPException(status_code=404, detail="Strategy not found")


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: str):
    """删除策略"""
    for i, s in enumerate(STRATEGIES):
        if s["id"] == strategy_id:
            STRATEGIES.pop(i)
            return {"ok": True, "id": strategy_id, "message": "策略已删除"}
    raise HTTPException(status_code=404, detail="Strategy not found")
