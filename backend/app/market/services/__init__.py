"""市场模块服务聚合（单例）。"""
from __future__ import annotations

from .quote_service import QuoteService

# 全局单例：行情服务（内含故障切换编排器）
quote_service = QuoteService()
