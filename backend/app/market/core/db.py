"""异步数据库层（SQLAlchemy 2.0 async）。

与平台既有「同步 SQLAlchemy + SQLite」完全解耦：独立引擎、独立 Base、独立库文件/库。
  * 本地开发：sqlite+aiosqlite:///./market.db（零依赖即可跑通）
  * 生产：    postgresql+asyncpg://user:pass@host:5432/quant（docker-compose 提供）

通过环境变量 MARKET_DB_URL 切换，业务代码无需改动。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """市场模块独立的 ORM 基类（不与平台同步 Base 混用）。"""


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine, _sessionmaker
    if _engine is None:
        url = settings.db_url
        kwargs: dict = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        # PostgreSQL 建议的连接池配置（支撑百万级标的并发写入）
        if url.startswith("postgresql"):
            kwargs.update(max_overflow=20, pool_size=10, pool_recycle=1800)
        _engine = create_async_engine(url, **kwargs)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
        logger.info("[market-db] 引擎已创建：%s", url.split("@")[-1] if "@" in url else url)
    return _engine


async def init_models() -> None:
    """建表（幂等）。在 lifespan 中调用一次。"""
    from . import models  # noqa: F401  确保模型被注册到 Base.metadata

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[market-db] 表结构已就绪")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每请求一个异步会话。"""
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """手动使用的异步会话上下文管理器（替代 `async with get_session()` 不可用的问题）。"""
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session
        await session.commit()
