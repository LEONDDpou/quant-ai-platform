"""行情数据源抽象层。

定义统一的 ``Quote`` 归一化结构与 ``QuoteSource`` 接口，使多数据源（腾讯/东财/新浪/AkShare/
券商 Level-2）可插拔、可故障切换。所有字段以 A 股 6 位代码为主键，外部输入 ``600519`` /
``sh600519`` / ``600519.SH`` 均可识别。
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    """归一化实时行情（跨数据源统一结构）。"""

    code: str
    name: str = ""
    price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0            # 成交量（手）
    amount: float = 0.0        # 成交额（元）
    turnover: float = 0.0      # 换手率 %
    pe: float = 0.0
    pb: float = 0.0
    total_mv: float = 0.0      # 总市值（元）
    float_mv: float = 0.0      # 流通市值（元）
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    source: str = ""
    ts: float = 0.0            # epoch 秒

    def to_dict(self) -> dict:
        return asdict(self)


_CODE_RE = re.compile(r"\d{4,6}")


def normalize_code(code: str) -> str:
    """将任意输入形式归一化为 6 位 A 股代码。失败返回原始串。"""
    code = (code or "").strip().upper()
    digits = "".join(ch for ch in code if ch.isdigit())
    digits = digits[-6:] if len(digits) >= 6 else digits
    return digits if digits else code


def vendor_symbol(code: str, vendor: str) -> str:
    """将代码转为各数据源所需形式。

    tencent/sina: sh600519 / sz000858 / bj830799
    eastmoney secid: 1.600519 / 0.000858 / 0.830799
    """
    code6 = normalize_code(code)
    if len(code6) != 6:
        return code
    lead = code6[0]
    if vendor in ("tencent", "sina"):
        if lead in ("6", "5", "9"):
            return "sh" + code6
        if lead in ("0", "3", "2"):
            return "sz" + code6
        if lead in ("4", "8"):
            return "bj" + code6
        return "sh" + code6
    if vendor == "eastmoney":
        if lead in ("6", "5", "9"):
            return "1." + code6
        # 深市 + 北交所统一用 0 前缀（北交所 secid 亦为 0.xxxxx）
        return "0." + code6
    return code6


class QuoteSource(ABC):
    """数据源接口。实现 ``fetch_quotes`` 即可接入故障切换编排器。"""

    name: str = "base"
    # 该源是否「可用」（如 AkShare 导入失败则为 False，编排器直接跳过）
    available: bool = True

    @abstractmethod
    async def fetch_quotes(self, codes: list[str]) -> dict[str, Quote]:
        """批量拉取行情，返回 {6位代码: Quote}。失败应抛异常由编排器捕获。"""

    async def health(self) -> bool:
        """健康探测（便宜调用）。默认返回 available。"""
        return self.available

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} name={self.name} available={self.available}>"
