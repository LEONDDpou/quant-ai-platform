"""K 线数据本地持久化缓存（#P1）。

KlineStore 作为 MarketProvider 的下层缓存：
1. 查本地 paper_kline_cache 表（SQLite）
2. 缺失的数据调用 westock-data 获取
3. 补充结果写入本地缓存
4. 回测引擎直接通过 KlineStore 获取 K 线，避免重复拉取
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_

from app.paper.domain_models import PaperKlineCache
from app.paper.repositories.base import BaseRepository


class _KlineRepo(BaseRepository):
    model = PaperKlineCache


class KlineStore:
    """K 线持久化缓存存储。"""

    def __init__(self):
        self.repo = _KlineRepo()

    def get_kline(self, code: str, period: str = "day",
                  limit: int = 120) -> list[dict]:
        """获取 K 线数据：优先缓存，缺失的自动拉取补齐。

        返回 [{date, open, high, low, close, volume}, ...]，按日期升序。
        """
        cached = self._get_cached(code, period, limit)
        need = limit - len(cached)
        if need > 0:
            fetched = self._fetch_and_store(code, period, need + 20)  # 多取 20 条以防边界
            if fetched:
                cached = self._get_cached(code, period, limit)
        return sorted(cached, key=lambda x: x["date"])

    def clear_old(self, days: int = 90):
        """清理指定天数前的缓存。"""
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        with self.repo._session() as db:
            db.query(PaperKlineCache).filter(
                PaperKlineCache.date < cutoff
            ).delete()
            db.commit()

    def count_cached(self, code: str = "") -> int:
        """统计缓存的 K 线条目数。"""
        if code:
            return len(self.repo.filter_by(code=code))
        return len(self.repo.list_all())

    # —— 内部 ——

    def _get_cached(self, code: str, period: str, limit: int) -> list[dict]:
        rows = self.repo.filter_by(code=code, period=period)
        rows.sort(key=lambda r: r.date, reverse=True)
        return [
            {"date": r.date, "open": r.open, "high": r.high,
             "low": r.low, "close": r.close, "volume": r.volume}
            for r in rows[:limit]
        ]

    def _fetch_and_store(self, code: str, period: str, limit: int) -> bool:
        """从 westock-data 拉取并落库。"""
        try:
            import subprocess, json
            period_map = {"day": "day", "week": "week", "month": "month"}
            cmd = [
                "westock-data", "kline", code,
                "--period", period_map.get(period, "day"),
                "--limit", str(limit),
                "--fq", "qfq",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return False

            # 解析 Markdown 表格输出
            lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
            # 找到表头下的数据行
            data_start = False
            for line in lines:
                if "|" not in line:
                    continue
                if not data_start:
                    if "日期" in line or "date" in line.lower():
                        data_start = True
                    continue
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) < 6:
                    continue
                try:
                    self.repo.add(PaperKlineCache(
                        code=code, date=parts[0],
                        open=float(parts[1]), high=float(parts[2]),
                        low=float(parts[3]), close=float(parts[4]),
                        volume=float(parts[5]), period=period,
                    ))
                except Exception:
                    continue  # 跳过重复行（唯一约束冲突）
            return True
        except Exception:
            return False
