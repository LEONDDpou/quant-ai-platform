"""模拟盘交易系统 — 统一业务异常。

业务层可预期错误（资金不足、持仓不足、订单不存在、风控拦截等）统一抛 PaperError，
由路由层捕获并转换为对应的 HTTP 状态码与错误信息，避免向调用方泄露底层异常细节。
"""


class PaperError(Exception):
    """业务层可预期错误。"""

    def __init__(self, message: str, code: str = "PAPER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)
