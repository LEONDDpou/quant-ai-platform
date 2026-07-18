"""可靠性原语：重试（指数退避）、熔断器、限流器。

设计目标（商业级）：
  * 不依赖第三方重试库，行为完全可控；
  * 熔断在「连续失败」时快速失败，避免对坏源反复打空请求；
  * 限流器保护下游（行情网关 / 交易所 API），防止被封。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"          # 正常放行
    OPEN = "open"              # 熔断中，快速失败
    HALF_OPEN = "half_open"    # 冷却结束，放行一次探测


class CircuitBreaker:
    """简单阈值熔断器。

    连续失败达到 ``fail_threshold`` 即进入 OPEN，经过 ``cooldown`` 秒后转为
    HALF_OPEN 放行一次探测；探测成功回到 CLOSED，失败则重新 OPEN。
    """

    def __init__(self, name: str, fail_threshold: int = 5, cooldown: float = 30.0):
        self.name = name
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and (time.monotonic() - self._opened_at) >= self.cooldown:
            self._state = CircuitState.HALF_OPEN
        return self._state

    def allow(self) -> bool:
        return self.state != CircuitState.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning("[CB:%s] 触发熔断（连续失败 %d 次）", self.name, self._failures)

    def __repr__(self) -> str:  # pragma: no cover
        return f"CircuitBreaker({self.name}={self.state.value})"


async def retry(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 2,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    on_exc: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """异步指数退避重试。

    :param attempts: 总尝试次数（含首次）。
    :param base_delay: 初始退避（秒），每次翻倍，封顶 max_delay。
    """
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await func()
        except on_exc as e:  # noqa: BLE001
            last = e
            if i == attempts - 1:
                break
            delay = min(base_delay * (2 ** i), max_delay)
            logger.debug("[retry] 第 %d 次失败：%s，%.2fs 后重试", i + 1, e, delay)
            await asyncio.sleep(delay)
    assert last is not None
    raise last


@dataclass
class RateLimiter:
    """令牌桶限流器（异步安全）。

    用于约束对行情网关 / 交易所 API 的请求频次，避免触发对方限流或封禁。
    """

    rate_per_sec: float = 10.0
    _tokens: float = field(default=0.0)
    _last: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self._tokens = self.rate_per_sec

    async def acquire(self, tokens: float = 1.0) -> None:
        while True:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self.rate_per_sec, self._tokens + elapsed * self.rate_per_sec)
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            wait = (tokens - self._tokens) / self.rate_per_sec
            await asyncio.sleep(max(wait, 0.0))
