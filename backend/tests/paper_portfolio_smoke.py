"""策略组合集成冒烟测试（打运行中的 :8000 后端）。"""
import json
import urllib.parse
import urllib.request

BASE = "http://localhost:8000"


def _req(method, path, data=None, timeout=60):
    url = BASE + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def _get_or_create_account():
    _, accounts = _req("GET", "/api/paper/account")
    if isinstance(accounts, list) and accounts:
        return accounts[0]["id"]
    _, acc = _req("POST", "/api/paper/account", {
        "name": "组合冒烟", "initialCapital": 1_000_000.0, "baseCurrency": "CNY",
    })
    return acc["id"]


def main():
    fails = 0

    account_id = _get_or_create_account()
    print(f"[1] account_id={account_id}")

    # 2) 创建组合
    status, pf = _req("POST", "/api/paper/portfolio", {
        "accountId": account_id,
        "name": "冒烟组合",
        "description": "集成测试组合",
        "allocation": [{"strategyId": "ai-001", "weight": 60}, {"strategyId": "ai-002", "weight": 40}],
        "totalCapital": 1_000_000,
        "enabled": True,
    })
    print(f"[2] create status={status} name={pf.get('name')} id={pf.get('id')} strategies={pf.get('strategyCount')}")
    assert status == 200 and pf.get("id"), "创建失败"
    pf_id = pf["id"]

    # 3) 列表
    status, lst = _req("GET", f"/api/paper/portfolio?account_id={account_id}")
    print(f"[3] list status={status} count={len(lst) if isinstance(lst, list) else '?'}")
    assert status == 200 and isinstance(lst, list) and len(lst) > 0

    # 4) 详情
    status, detail = _req("GET", f"/api/paper/portfolio/{pf_id}")
    print(f"[4] detail status={status} name={detail.get('name')}")
    assert status == 200 and detail.get("id") == pf_id

    # 5) 更新
    status, updated = _req("PUT", f"/api/paper/portfolio/{pf_id}", {
        "accountId": account_id,
        "name": "更新组合",
        "allocation": [{"strategyId": "ai-001", "weight": 100}],
        "totalCapital": 2_000_000,
        "enabled": True,
    })
    print(f"[5] update status={status} name={updated.get('name')} capital={updated.get('totalCapital')}")
    assert status == 200 and updated.get("totalCapital") == 2_000_000

    # 6) 再平衡
    status, rb = _req("POST", f"/api/paper/portfolio/{pf_id}/rebalance?reason={urllib.parse.quote('冒烟再平衡')}", {
        "accountId": account_id,
        "name": "再平衡组合",
        "allocation": [{"strategyId": "ai-001", "weight": 50}, {"strategyId": "ai-003", "weight": 50}],
        "totalCapital": 2_000_000,
    })
    print(f"[6] rebalance status={status} reason={rb.get('reason')} status={rb.get('status')}")
    assert status == 200 and rb.get("status") == "done"

    # 7) 再平衡历史
    status, rbs = _req("GET", f"/api/paper/portfolio/{pf_id}/rebalances?limit=10")
    print(f"[7] rebalances status={status} count={len(rbs) if isinstance(rbs, list) else '?'}")
    assert status == 200 and len(rbs) >= 1

    # 8) 删除
    status, del_resp = _req("DELETE", f"/api/paper/portfolio/{pf_id}")
    print(f"[8] delete status={status} deleted={del_resp.get('deleted')}")
    assert status == 200 and del_resp.get("deleted") is True

    print("\nALL PORTFOLIO SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
