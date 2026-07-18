"""模拟盘交易系统 — M8 回测仓储。

围绕回测记录表 ``backtest_runs`` 的持久化：
- 保存一次回测结果（落库供历史查询）；
- 按账户 / 全局列出历史回测；
- 按 id 取单次回测详情。
"""
from typing import List, Optional

from app.paper.domain_models import BacktestRun
from app.paper.repositories.base import BaseRepository


class BacktestRepository(BaseRepository):
    """回测记录（backtest_runs）持久化。"""

    model = BacktestRun

    def save(self, run: BacktestRun) -> BacktestRun:
        """落库一条回测记录并返回（含自增 id）。"""
        return self.add(run)

    def list_runs(
        self,
        account_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[BacktestRun]:
        """列出回测历史，默认按时间倒序。account_id 为空时返回全部账户。"""
        with self._session() as db:
            q = db.query(BacktestRun)
            if account_id is not None:
                q = q.filter(BacktestRun.account_id == account_id)
            return q.order_by(BacktestRun.created_at.desc()).limit(limit).all()

    def get(self, run_id: int) -> Optional[BacktestRun]:
        """按 id 取回测记录。"""
        return super().get(run_id)
