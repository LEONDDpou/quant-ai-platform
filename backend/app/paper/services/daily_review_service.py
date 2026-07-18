"""AI 每日复盘报告服务（#186）。

收集模拟盘账户的今日成交、持仓变动、盈亏归因，结合市场概况，
生成结构化复盘报告并落库。LLM 优先（复用 llm_service.generate_report），
失败回退规则合成。
"""
import datetime
from typing import List, Optional

from app.paper.domain_models import PaperDailyReview
from app.paper.errors import PaperError
from app.paper.repositories.base import BaseRepository
from app.paper.repositories.account_repo import AccountRepository
from app.paper.schemas import DailyReviewResponse


class _ReviewRepo(BaseRepository):
    model = PaperDailyReview


class DailyReviewService:
    """每日复盘服务。"""

    def __init__(self):
        self.repo = _ReviewRepo()
        self.acct_repo = AccountRepository()

    def get_latest(self, account_id: int) -> Optional[DailyReviewResponse]:
        """获取某账户最新复盘。"""
        objs = self.repo.filter_by(account_id=account_id)
        if not objs:
            return None
        objs.sort(key=lambda o: o.created_at or datetime.datetime.min, reverse=True)
        return self._to_resp(objs[0])

    def list_reviews(self, account_id: int, limit: int = 20) -> List[DailyReviewResponse]:
        """获取某账户复盘历史。"""
        objs = self.repo.filter_by(account_id=account_id)
        objs.sort(key=lambda o: o.created_at or datetime.datetime.min, reverse=True)
        return [self._to_resp(o) for o in objs[:limit]]

    def generate_review(self, account_id: int) -> DailyReviewResponse:
        """生成今日复盘报告（规则确定性）。"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        # 收集账户数据
        acct = self.acct_repo.get_account(account_id)
        if not acct:
            raise PaperError(f"账户不存在: {account_id}")

        # 今日成交汇总
        from app.paper.domain_models import PaperOrder
        base = BaseRepository()
        base.model = PaperOrder
        orders = base.filter_by(account_id=account_id) or []
        today_orders = [o for o in orders if o.created_at and o.created_at.strftime("%Y-%m-%d") == today]
        buys = [o for o in today_orders if o.direction == "buy" and o.status == "filled"]
        sells = [o for o in today_orders if o.direction == "sell" and o.status == "filled"]
        trades_summary = {
            "totalOrders": len(today_orders),
            "filledBuys": len(buys),
            "filledSells": len(sells),
            "buyAmount": round(sum((o.price or 0) * (o.filled_quantity or 0) for o in buys), 2),
            "sellAmount": round(sum((o.price or 0) * (o.filled_quantity or 0) for o in sells), 2),
        }

        # 持仓概况
        positions = self.acct_repo.list_positions(account_id)
        pos_count = len(positions or [])
        total_pos_val = sum((p.current_price or 0) * (p.shares or 0) for p in (positions or []))
        total_cost = sum((p.cost_price or 0) * (p.shares or 0) for p in (positions or []))

        pnl_summary = {
            "todayPnl": round(acct.today_pnl or 0, 2),
            "totalPnl": round((acct.total_assets or 0) - acct.initial_capital, 2),
            "positionCount": pos_count,
            "positionValue": round(total_pos_val, 2),
            "totalCost": round(total_cost, 2),
            "unrealizedPnl": round(total_pos_val - total_cost, 2),
        }

        performance = {
            "totalAssets": round(acct.total_assets or 0, 2),
            "cash": round(acct.cash or 0, 2),
            "positionRatio": round(acct.position_ratio or 0, 2),
            "winRate": round(acct.win_rate or 0, 2),
        }

        # 决策回顾（最近成交）
        decisions = []
        for o in today_orders[:10]:
            decisions.append({
                "code": o.code,
                "direction": o.direction,
                "price": o.price,
                "shares": o.filled_quantity or 0,
                "status": o.status,
                "reason": getattr(o, "remark", ""),
            })

        # 市场概况（尝试从 llm_service 获取，失败用简单文本）
        market_summary = ""
        try:
            from app.services import llm_service as llm
            report = llm.generate_report()
            if report and isinstance(report, dict):
                market_summary = report.get("marketSummary", "") or ""
        except Exception:
            pass
        if not market_summary:
            market_summary = f"{today} 市场运行平稳。"

        # 生成复盘总结文本
        total_pnl = pnl_summary["todayPnl"]
        pos_ratio = performance["positionRatio"]
        summary_parts = [
            f"📊 今日{'盈利' if total_pnl >= 0 else '亏损'} {abs(total_pnl):.0f} 元",
            f" | 仓位 {pos_ratio:.0f}%",
            f" | 持仓 {pos_count} 只",
            f" | 成交 {trades_summary['filledBuys']} 笔买入 / {trades_summary['filledSells']} 笔卖出",
        ]
        if pos_count > 0:
            top_pos = positions[0]
            summary_parts.append(f" | 重仓 {top_pos.code}")

        # 持久化
        review = PaperDailyReview(
            account_id=account_id,
            date=today,
            summary="".join(summary_parts),
            trades_summary=trades_summary,
            market_summary=market_summary,
            pnl_summary=pnl_summary,
            performance=performance,
            decisions=decisions,
            generated_by="rule",
        )
        self.repo.add(review)
        return self._to_resp(review)

    def _to_resp(self, obj: PaperDailyReview) -> DailyReviewResponse:
        return DailyReviewResponse(
            id=obj.id,
            accountId=obj.account_id,
            date=obj.date,
            summary=obj.summary or "",
            tradesSummary=obj.trades_summary or {},
            marketSummary=obj.market_summary or "",
            pnlSummary=obj.pnl_summary or {},
            performance=obj.performance or {},
            decisions=obj.decisions or [],
            generatedBy=obj.generated_by or "rule",
            createdAt=obj.created_at.isoformat() if obj.created_at else "",
        )
