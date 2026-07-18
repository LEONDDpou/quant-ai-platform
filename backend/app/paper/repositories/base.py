"""模拟盘交易系统 — 仓储基类（Repository Pattern）。

约定（与平台 crud 风格一致，但面向「仓储对象」而非散函数）：
- 默认每个仓储方法独立开/关 Session（无外部 session 时），便于在路由或
  asyncio.to_thread 中安全调用；
- 支持注入外部 Session（服务层事务场景），此时由调用方负责关闭；
- 读操作失败返回 None / 空列表；写操作异常向上抛 PaperError，由上层统一转换。
"""
from contextlib import contextmanager
from typing import Optional, Type

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.paper.errors import PaperError


class BaseRepository:
    """泛型仓储基类。子类设置 model 即可获得通用 CRUD。"""

    model: Type = None

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    # —— Session 管理 ——
    @contextmanager
    def _session(self):
        if self._db is not None:
            yield self._db
            return
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # —— 通用读写 ——
    def add(self, obj):
        with self._session() as db:
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj

    def get(self, pk):
        with self._session() as db:
            return db.get(self.model, pk)

    def list_all(self, limit: int = 100):
        with self._session() as db:
            return db.query(self.model).limit(limit).all()

    def filter_by(self, **kwargs):
        with self._session() as db:
            return db.query(self.model).filter_by(**kwargs).all()

    def update(self, pk, **fields):
        with self._session() as db:
            obj = db.get(self.model, pk)
            if not obj:
                raise PaperError(f"记录不存在: {self.model.__name__}#{pk}")
            for k, v in fields.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            db.commit()
            db.refresh(obj)
            return obj

    def delete(self, pk):
        with self._session() as db:
            obj = db.get(self.model, pk)
            if not obj:
                return False
            db.delete(obj)
            db.commit()
            return True
