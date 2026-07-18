"""数据库核心 — SQLAlchemy 2.0 同步引擎。

设计要点：
- 同一套 ORM 模型同时兼容 SQLite（本沙箱验证用）与 PostgreSQL（生产目标），
  通过环境变量 DATABASE_URL 切换，无需改代码。
  - 本地验证：DATABASE_URL=sqlite:///./quant.db
  - 生产部署：DATABASE_URL=postgresql+psycopg://user:pass@host:5432/quantdb
- 使用同步引擎 + sessionmaker；FastAPI 的 `def` 路由会在线程池中执行，
  WebSocket 推送循环则用 asyncio.to_thread 写库，避免阻塞事件循环。
- JSON 列用 sqlalchemy.JSON，SQLite / PostgreSQL 均原生支持；模型刻意不用
  ARRAY 等 PG 专有类型，保证可移植。
"""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ============================================================
# 连接配置
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./quant.db").strip()

_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    # SQLite 跨线程需要此参数（线程池 / to_thread 写库）
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

Base = declarative_base()


def init_db() -> None:
    """建表（幂等）。在应用启动时调用一次。"""
    # 确保模型已注册到 Base.metadata
    from app.db import models  # noqa: F401
    from app.paper import domain_models  # noqa: F401  # 注册模拟盘交易系统 ORM

    Base.metadata.create_all(bind=engine)

    # 补齐已存在表的 M3 新增列（幂等，不影响既有数据）
    from app.paper.migrate import migrate_paper_schema
    migrate_paper_schema()


def get_db():
    """FastAPI 依赖：每个请求一个 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
