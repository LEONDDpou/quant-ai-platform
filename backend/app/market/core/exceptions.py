"""市场模块异常体系。"""
from __future__ import annotations


class MarketError(Exception):
    """市场模块基础异常。"""


class SourceUnavailableError(MarketError):
    """所有配置的数据源均不可用。"""

    def __init__(self, message: str = "所有数据源均不可用", tried: list[str] | None = None):
        self.tried = tried or []
        super().__init__(f"{message} (tried={self.tried})")


class SourceTimeoutError(MarketError):
    """单数据源请求超时。"""


class ParseError(MarketError):
    """数据源返回内容无法解析。"""


class RateLimitExceeded(MarketError):
    """触发全局限速。"""


class ValidationError(MarketError):
    """数据异常检测未通过（如价格为负、涨跌幅越界）。"""
