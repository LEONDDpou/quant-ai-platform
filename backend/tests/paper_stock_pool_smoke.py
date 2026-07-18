"""模拟盘交易系统 — 股票池自动维护集成冒烟（直连 :8000 运行中的后端）。

走完整链路：同步源下拉 → 配置 → 新增标的 → 列表 → 立即维护(同步成分) →
变更日志 → 清理。任一环节非 200 / 字段缺失即报错。

运行：cd backend && PYTHONPATH=. python tests/paper_stock_pool_smoke.py
"""
import json
import sys
import urllib.request

BASE = "http://localhost:8000"


def _req(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def ok(cond, msg):
    if not cond:
        print(f"[FAIL] {msg}")
        sys.exit(1)
    print(f"[ok] {msg}")


def main():
    # 0) 取一个演示账户
    _, accts = _req("GET", "/api/paper/account")
    ok(isinstance(accts, list) and len(accts) > 0, "account list 非空")
    aid = accts[0]["id"]
    ok(isinstance(aid, int), f"account id={aid}")

    # 1) 同步源下拉
    _, sources = _req("GET", "/api/paper/pool/sources")
    ok("sector" in sources and "concept" in sources, "sources 含 sector/concept")

    # 2) 配置：启用板块自动同步（白酒）
    _, cfg = _req("PUT", f"/api/paper/pool/{aid}/config", {
        "autoSync": True, "syncSource": "sector", "syncName": "白酒",
        "removeSuspended": True, "removeSt": True, "removeIlliquid": False,
        "minTurnover": 1.0, "maxSize": 0,
    })
    ok(cfg.get("autoSync") is True and cfg.get("syncName") == "白酒", "PUT config 生效")

    # 3) 新增标的（手动）
    _, item = _req("POST", f"/api/paper/pool/{aid}/items", {"code": "600519", "name": "贵州茅台", "category": "核心仓"})
    ok(item.get("code") == "600519", f"POST item code={item.get('code')}")
    manual_id = item["id"]

    # 4) 列表
    _, items = _req("GET", f"/api/paper/pool/{aid}/items")
    ok(isinstance(items, list) and len(items) >= 1, f"GET items count={len(items)}")

    # 5) 立即维护（应同步白酒成分新增若干）
    _, res = _req("POST", f"/api/paper/pool/{aid}/maintain", {})
    ok("added" in res and "removed" in res and "checked" in res, f"maintain added={res.get('added')} removed={res.get('removed')}")
    ok(res.get("added", 0) >= 1, f"maintain 新增成分 added={res.get('added')}")

    # 6) 变更日志含新增记录
    _, logs = _req("GET", f"/api/paper/pool/{aid}/changelog")
    ok(isinstance(logs, list) and len(logs) >= 1, f"changelog count={len(logs)}")

    # 7) 清理：移除手动添加的标的
    _, delr = _req("DELETE", f"/api/paper/pool/{aid}/items/{manual_id}")
    ok(delr.get("deleted") is True, "DELETE item 成功")

    print("\nALL STOCK POOL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
