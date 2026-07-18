"""模拟盘交易系统 — M179 股票池自动维护服务层。

职责：
- 股票池标的的增删改查（含锁定 / 分组 / 来源）；
- 账户级自动维护配置（同步源 / 自动移除规则）；
- 后台自动维护核心逻辑：从板块/指数自动同步成分 + 健康检测（停牌/ST/流动性）
  + 按规则自动移除（锁定标的豁免）+ 全量变更留痕；
- 板块成分获取：真实源（AKShare）优先，无网/失败时回退内置已知板块映射，
  保证沙箱环境也能演示自动同步效果。

设计原则：
- 纯确定性逻辑（健康判定、规则匹配、变更留痕）与网络调用解耦，便于单测；
- 所有外部行情/板块接口调用均 try/except 包裹，单标的异常不影响整体循环。
"""
from datetime import datetime
from typing import Dict, List, Optional

from app.paper.domain_models import (
    PaperPoolChangeLog,
    PaperPoolConfig,
    Watchlist,
)
from app.paper.repositories.pool_repo import (
    PoolChangeLogRepository,
    PoolConfigRepository,
    PoolItemRepository,
)
from app.paper.schemas import (
    PoolChangeLogResponse,
    PoolConfigRequest,
    PoolConfigResponse,
    PoolItemRequest,
    PoolItemResponse,
    PoolMaintainResult,
)
from app.paper.errors import PaperError
from app.paper.services.market_provider import market_provider


def _try_akshare():
    """惰性导入 AKShare；不可用时返回 None。"""
    try:
        import akshare as ak  # noqa: F401
        return ak
    except Exception:
        return None


# 已知板块 → 成分代码映射（沙箱/无网环境的回退同步源，保证演示可用）
_KNOWN_INDUSTRY: Dict[str, List[str]] = {
    "白酒": ["600519", "000858", "000568", "002304", "600779"],
    "半导体": ["688981", "603501", "002049", "600584", "300782"],
    "新能源车": ["002594", "300750", "601127", "600733", "002460"],
    "券商": ["600030", "600837", "601688", "000776", "601211"],
    "银行": ["601398", "601939", "600036", "601288", "600000"],
    "医药": ["600276", "300760", "000661", "600196", "002821"],
    "光伏": ["601012", "300274", "600438", "002129", "688599"],
}
_KNOWN_CONCEPT: Dict[str, List[str]] = {
    "人工智能": ["002230", "300308", "688256", "000977", "300624"],
    "ChatGPT": ["300308", "002230", "688111", "300624", "002415"],
    "锂电池": ["300750", "002460", "300014", "002245", "600884"],
    "华为概念": ["002475", "000063", "300136", "002241", "601138"],
    "机器人": ["300024", "002472", "688169", "300607", "002747"],
}


class PoolMaintenanceService:
    """股票池自动维护服务。"""

    def __init__(self):
        self.item_repo = PoolItemRepository()
        self.config_repo = PoolConfigRepository()
        self.log_repo = PoolChangeLogRepository()
        self.market_provider = market_provider

    # ===================== 标的 CRUD =====================
    def list_items(self, account_id: int) -> List[PoolItemResponse]:
        rows = self.item_repo.list_items(account_id)
        return [self._item_to_resp(r) for r in rows]

    def add_item(self, account_id: int, req: PoolItemRequest) -> PoolItemResponse:
        code = (req.code or "").strip()
        if not code:
            raise PaperError("股票代码不能为空")
        if self.item_repo.get_by_code(account_id, code):
            raise PaperError(f"股票池已包含 {code}")
        row = self._create_item(
            account_id, code, req.name, req.category, req.note, req.pinned, req.source or "manual"
        )
        self._log(account_id, code, req.name, "add", "手动添加", req.source or "manual")
        return self._item_to_resp(row)

    def remove_item(self, item_id: int) -> bool:
        row = self.item_repo.get(item_id)
        if not row:
            raise PaperError(f"标的不存在 #{item_id}")
        code, name, src, acct = row.code, row.name or "", row.source, row.account_id
        ok = self.item_repo.delete(item_id)
        if ok:
            self._log(acct, code, name, "remove", "手动移除", src)
        return ok

    def update_item(self, item_id: int, category=None, note=None, pinned=None) -> PoolItemResponse:
        fields = {}
        if category is not None:
            fields["category"] = category
        if note is not None:
            fields["note"] = note
        if pinned is not None:
            fields["pinned"] = bool(pinned)
        row = self.item_repo.update(item_id, **fields)
        if not row:
            raise PaperError(f"标的不存在 #{item_id}")
        return self._item_to_resp(row)

    # ===================== 配置 CRUD =====================
    def get_config(self, account_id: int) -> PoolConfigResponse:
        cfg = self.config_repo.get_by_account(account_id)
        if not cfg:
            return PoolConfigResponse(
                accountId=account_id, autoSync=False, syncSource="manual", syncName="",
                removeSuspended=True, removeSt=True, removeIlliquid=False,
                minTurnover=1.0, maxSize=0, updatedAt=None,
            )
        return self._config_to_resp(cfg)

    def upsert_config(self, account_id: int, req: PoolConfigRequest) -> PoolConfigResponse:
        cfg = self.config_repo.upsert(
            account_id,
            auto_sync=req.autoSync,
            sync_source=req.syncSource,
            sync_name=req.syncName,
            remove_suspended=req.removeSuspended,
            remove_st=req.removeSt,
            remove_illiquid=req.removeIlliquid,
            min_turnover=req.minTurnover,
            max_size=req.maxSize,
        )
        return self._config_to_resp(cfg)

    # ===================== 变更日志 =====================
    def get_changelog(self, account_id: int, limit: int = 100) -> List[PoolChangeLogResponse]:
        logs = self.log_repo.list_recent(account_id, limit=limit)
        return [self._log_to_resp(l) for l in logs]

    # ===================== 同步源列表（前端下拉） =====================
    def list_sources(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {
            "sector": list(_KNOWN_INDUSTRY.keys()),
            "concept": list(_KNOWN_CONCEPT.keys()),
        }
        # 真实源可用时补充市场实际板块名（供手工选择同步）
        ak = _try_akshare()
        if ak is not None:
            for kind in ("industry", "concept"):
                try:
                    if kind == "industry":
                        df = ak.stock_board_industry_name_em()
                    else:
                        df = ak.stock_board_concept_name_em()
                    if df is not None and not df.empty and "板块名称" in df.columns:
                        for n in df["板块名称"].tolist():
                            n = str(n)
                            if n not in out[kind]:
                                out[kind].append(n)
                except Exception:
                    pass
        return out

    # ===================== 核心：自动维护 =====================
    def run_maintenance(self, account_id: int) -> PoolMaintainResult:
        """执行一次自动维护：同步成分 + 健康检测 + 按规则移除 + 变更留痕。"""
        # 取 ORM 配置对象（snake_case 字段，便于内部逻辑直接读取；无记录则用默认值）
        cfg = self.config_repo.get_by_account(account_id)
        if cfg is None:
            # 仅构造瞬时对象，列默认值不会在实例化时生效，故显式给出
            cfg = PaperPoolConfig(
                account_id=account_id,
                auto_sync=False, sync_source="manual", sync_name="",
                remove_suspended=True, remove_st=True, remove_illiquid=False,
                min_turnover=1.0, max_size=0,
            )
        items = self.item_repo.list_items(account_id)
        existing_codes = {it.code for it in items}
        details: List[dict] = []
        added = removed = skipped_pinned = checked = 0

        # —— 1) 自动同步成分（板块/指数 → 股票池）——
        if cfg.auto_sync and cfg.sync_source != "manual" and cfg.sync_name:
            cons = self._fetch_constituents(cfg.sync_source, cfg.sync_name)
            for code in cons:
                if code in existing_codes:
                    continue
                if cfg.max_size and (len(existing_codes) + added) >= cfg.max_size:
                    break
                self._create_item(
                    account_id, code, "", "", "", False, f"sync:{cfg.sync_name}"
                )
                existing_codes.add(code)
                added += 1
                reason = f"板块同步新增（{cfg.sync_name}）"
                self._log(account_id, code, "", "add", reason, f"sync:{cfg.sync_name}")
                details.append({"code": code, "action": "add", "reason": reason})

        # —— 2) 健康检测 + 按规则自动移除 ——
        for it in items:
            checked += 1
            try:
                quote = self.market_provider.quote(it.code)
            except Exception:
                quote = None
            health = self._detect_health(it.code, quote, cfg)
            self.item_repo.update(it.id, health=health, last_checked=datetime.utcnow())

            if health in ("suspended", "st", "illiquid"):
                rule_on = {
                    "suspended": cfg.remove_suspended,
                    "st": cfg.remove_st,
                    "illiquid": cfg.remove_illiquid,
                }[health]
                if not rule_on:
                    continue
                if it.pinned:
                    skipped_pinned += 1
                    details.append({"code": it.code, "action": "skip",
                                    "reason": f"{health} 但已锁定"})
                    continue
                self.item_repo.delete(it.id)
                removed += 1
                reason = f"自动移除：{health}"
                self._log(account_id, it.code, it.name or "", "remove", reason, it.source)
                details.append({"code": it.code, "action": "remove", "reason": reason})

        return PoolMaintainResult(
            accountId=account_id, checked=checked, added=added,
            removed=removed, skippedPinned=skipped_pinned, details=details,
        )

    # ===================== 内部工具 =====================
    def _fetch_constituents(self, source: str, name: str) -> List[str]:
        """获取板块/指数成分代码（6 位）。真实源优先，失败回退已知板块映射。"""
        if source in ("sector", "concept"):
            ak = _try_akshare()
            if ak is not None:
                try:
                    if source == "sector":
                        df = ak.stock_board_industry_cons_em(symbol=name)
                    else:
                        df = ak.stock_board_concept_cons_em(symbol=name)
                    if df is not None and not df.empty and "代码" in df.columns:
                        return [str(c) for c in df["代码"].tolist()]
                except Exception:
                    pass
        # 回退：已知板块映射
        if source == "concept":
            return list(_KNOWN_CONCEPT.get(name, []))
        return list(_KNOWN_INDUSTRY.get(name, []))

    @staticmethod
    def _is_st(name: str) -> bool:
        if not name:
            return False
        n = name.upper()
        return n.startswith("*ST") or n.startswith("ST") or n.startswith("S")

    def _detect_health(self, code: str, quote: Optional[dict], cfg) -> str:
        """根据行情判定标的健康状态。"""
        if quote is None:
            return "suspended"
        name = quote.get("name") or ""
        if self._is_st(name):
            return "st"
        # 流动性仅在真实数据源下判定（模拟源换手率为随机值，不具参考意义）
        if quote.get("dataSource") == "akshare":
            try:
                turnover = float(quote.get("turnover") or 0)
            except (TypeError, ValueError):
                turnover = 0.0
            if turnover < cfg.min_turnover:
                return "illiquid"
        return "ok"

    def _create_item(self, account_id, code, name, category, note, pinned, source) -> Watchlist:
        row = Watchlist(
            account_id=account_id, code=code, name=name or "", category=category or "",
            note=note or "", pinned=bool(pinned), source=source or "manual",
        )
        return self.item_repo.add(row)

    def _log(self, account_id, code, name, action, reason, source) -> None:
        log = PaperPoolChangeLog(
            account_id=account_id, code=code or "", name=name or "",
            action=action, reason=reason or "", source=source or "manual",
        )
        self.log_repo.add(log)

    @staticmethod
    def _item_to_resp(it: Watchlist) -> PoolItemResponse:
        return PoolItemResponse(
            id=it.id, accountId=it.account_id, code=it.code, name=it.name or "",
            category=it.category or "", note=it.note or "", pinned=bool(it.pinned),
            health=it.health or "unknown", source=it.source or "manual",
            lastChecked=it.last_checked.isoformat() if it.last_checked else None,
            createdAt=it.created_at.isoformat() if it.created_at else "",
        )

    @staticmethod
    def _config_to_resp(cfg: PaperPoolConfig) -> PoolConfigResponse:
        return PoolConfigResponse(
            accountId=cfg.account_id, autoSync=bool(cfg.auto_sync),
            syncSource=cfg.sync_source or "manual", syncName=cfg.sync_name or "",
            removeSuspended=bool(cfg.remove_suspended), removeSt=bool(cfg.remove_st),
            removeIlliquid=bool(cfg.remove_illiquid), minTurnover=float(cfg.min_turnover),
            maxSize=int(cfg.max_size),
            updatedAt=cfg.updated_at.isoformat() if cfg.updated_at else None,
        )

    @staticmethod
    def _log_to_resp(l: PaperPoolChangeLog) -> PoolChangeLogResponse:
        return PoolChangeLogResponse(
            id=l.id, accountId=l.account_id, code=l.code or "", name=l.name or "",
            action=l.action or "", reason=l.reason or "", source=l.source or "",
            createdAt=l.created_at.isoformat() if l.created_at else "",
        )
