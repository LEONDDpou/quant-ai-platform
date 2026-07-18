"""AkShare 实时行情源（最后兜底源）。

已知风险：AkShare 在 uvloop 事件循环下导入会抛 ``Can't patch loop``，且 ``stock_zh_a_spot_em``
走东方财富接口在本沙箱经代理返回 502。为保证平台「任何环境可降级运行」，此处：
  * 惰性导入——仅在初始化时尝试 ``import akshare``，失败则 ``available=False``，编排器直接跳过；
  * 重计算在 ``asyncio.to_thread`` 内执行，不触碰主事件循环，规避 uvloop 冲突；
  * 作为故障切换链的最末位，仅当前面所有源都不可用时才启用。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .base import Quote, QuoteSource, normalize_code

logger = logging.getLogger(__name__)


class AkShareSource(QuoteSource):
    name = "akshare"
    available: bool = False
    _ak = None

    def __init__(self) -> None:
        try:
            import akshare as ak  # noqa: PLC0415

            self._ak = ak
            self.available = True
        except Exception as e:  # noqa: BLE001
            logger.warning("[akshare_src] 不可用（导入失败，将跳过）: %s", e)
            self.available = False

    async def health(self) -> bool:
        return self.available

    async def fetch_quotes(self, codes: list[str]) -> dict[str, Quote]:
        if not self.available or self._ak is None:
            raise RuntimeError("akshare unavailable")

        want = {normalize_code(c) for c in codes}
        try:
            df = await asyncio.to_thread(self._ak.stock_zh_a_spot_em)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"akshare spot failed: {e}") from e

        cols = {c: i for i, c in enumerate(df.columns)}
        out: dict[str, Quote] = {}

        def _col(*names: str):
            for n in names:
                if n in cols:
                    return cols[n]
            return -1

        i_code = _col("代码")
        i_name = _col("名称")
        i_price = _col("最新价")
        i_pct = _col("涨跌幅")
        i_chg = _col("涨跌额")
        i_vol = _col("成交量")
        i_amt = _col("成交额")
        i_turn = _col("换手率")
        i_pe = _col("市盈率-动态", "市盈率(动)")
        i_pb = _col("市净率")
        i_tmv = _col("总市值")
        i_fmv = _col("流通市值")

        def _num(row, idx, default=0.0):
            if idx < 0:
                return default
            try:
                return float(row[idx])
            except (ValueError, TypeError):
                return default

        for row in df.itertuples(index=False, name=None):
            code = str(row[i_code]).strip().zfill(6) if i_code >= 0 else ""
            if code not in want:
                continue
            try:
                price = _num(row, i_price)
                pct = _num(row, i_pct)
                out[code] = Quote(
                    code=code,
                    name=str(row[i_name]) if i_name >= 0 else "",
                    price=price,
                    change=_num(row, i_chg),
                    change_pct=pct,
                    volume=int(_num(row, i_vol)),
                    amount=_num(row, i_amt),
                    turnover=_num(row, i_turn),
                    pe=_num(row, i_pe),
                    pb=_num(row, i_pb),
                    total_mv=_num(row, i_tmv),
                    float_mv=_num(row, i_fmv),
                    source="akshare",
                    ts=__import__("time").time(),
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("[akshare_src] 解析行失败 code=%s: %s", code, e)
        if not out:
            raise RuntimeError("akshare returned empty")
        return out
