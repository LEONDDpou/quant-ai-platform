"""研究员 Agent 集成冒烟（打运行中的 :8000 后端）。

链路：取/建账户 → 运行研究（挖因子+生成策略）→ 列举会话 → 列举想法 →
对想法触发回测 → 校验回测结果字段 → 删除想法。
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def _req(method, path, data=None, timeout=120):
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
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def _get_or_create_account():
    _, accounts = _req("GET", "/api/paper/account")
    if isinstance(accounts, list) and accounts:
        return accounts[0]["id"]
    _, acc = _req("POST", "/api/paper/account", {
        "name": "研究员冒烟账户", "initialCapital": 1000000.0, "baseCurrency": "CNY",
    })
    return acc["id"]


def main():
    fails = 0

    # 1) 账户
    account_id = _get_or_create_account()
    print(f"[1] account_id={account_id}")
    assert account_id, "账户获取失败"

    # 2) 运行研究
    status, run = _req("POST", "/api/paper/research/run", {
        "accountId": account_id,
        "universe": ["600519", "300750", "601318"],
        "useLlm": False,
        "maxIdeas": 3,
    })
    print(f"[2] research/run status={status} factors={run.get('factorCount')} ideas={run.get('ideaCount')}")
    assert status == 200 and run.get("factorCount", 0) > 0 and run.get("ideaCount", 0) > 0

    # 3) 会话列表
    status, sessions = _req("GET", f"/api/paper/research/sessions?account_id={account_id}")
    print(f"[3] sessions status={status} count={len(sessions) if isinstance(sessions, list) else '?'}")
    assert status == 200 and isinstance(sessions, list) and len(sessions) > 0

    # 4) 想法列表
    status, ideas = _req("GET", f"/api/paper/research/ideas?account_id={account_id}")
    print(f"[4] ideas status={status} count={len(ideas) if isinstance(ideas, list) else '?'}")
    assert status == 200 and isinstance(ideas, list) and len(ideas) > 0
    idea_id = ideas[0]["id"]

    # 5) 回测想法
    status, bt = _req("POST", f"/api/paper/research/ideas/{idea_id}/backtest?account_id={account_id}")
    print(f"[5] backtest status={status} runId={bt.get('runId')} totalReturn={bt.get('totalReturn')} trades={bt.get('totalTrades')}")
    assert status == 200 and bt.get("runId") and "totalReturn" in bt

    # 6) 想法详情（应标记已回测）
    status, idea_detail = _req("GET", f"/api/paper/research/ideas/{idea_id}")
    print(f"[6] idea detail status={status} backtested={idea_detail.get('backtested')}")
    assert status == 200 and idea_detail.get("backtested") is True

    # 7) 删除想法
    status, dele = _req("DELETE", f"/api/paper/research/ideas/{idea_id}")
    print(f"[7] delete status={status} deleted={dele.get('deleted')}")
    assert status == 200 and dele.get("deleted") is True

    if fails == 0:
        print("\nALL RESEARCH AGENT SMOKE CHECKS PASSED")
    else:
        print(f"\n{fn(fails)} CHECK(S) FAILED")
        sys.exit(1)


def fn(n):
    return f"{n}"


if __name__ == "__main__":
    main()
