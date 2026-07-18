"""策略市场集成冒烟测试（打运行中的 :8000 后端）。"""
import json
from urllib.parse import quote
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
    status, accounts = _req("GET", "/api/paper/account")
    if isinstance(accounts, list) and accounts:
        return accounts[0]["id"]
    _, acc = _req("POST", "/api/paper/account", {
        "name": "策略市场冒烟", "initialCapital": 1_000_000.0, "baseCurrency": "CNY",
    })
    return acc["id"]


def main():
    fails = 0

    account_id = _get_or_create_account()
    print(f"[1] account_id={account_id}")
    assert account_id, "账户获取失败"

    # 2) 发布策略
    status, pub = _req("POST", "/api/paper/strategy-marketplace/publish", {
        "accountId": account_id,
        "name": "冒烟测试策略",
        "description": "集成测试用",
        "sourceType": "manual",
        "entryRules": [{"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}}],
        "exitRules": [],
        "tags": ["测试", "冒烟"],
    })
    print(f"[2] publish status={status} name={pub.get('name')} id={pub.get('id')}")
    assert status == 200 and pub.get("id"), "发布失败"
    pub_id = pub["id"]

    # 3) 浏览列表
    status, listings = _req("GET", "/api/paper/strategy-marketplace/listing?limit=10")
    print(f"[3] listing status={status} count={len(listings) if isinstance(listings, list) else '?'}")
    assert status == 200 and isinstance(listings, list) and len(listings) > 0

    # 4) 搜索（中文需 URL 编码）
    tag_encoded = quote("冒烟")
    status, results = _req("GET", f"/api/paper/strategy-marketplace/search?tag={tag_encoded}&limit=10")
    print(f"[4] search status={status} count={len(results) if isinstance(results, list) else '?'}")
    assert status == 200 and len(results) >= 1

    # 5) 订阅
    status, sub = _req("POST", "/api/paper/strategy-marketplace/subscribe", {
        "accountId": account_id,
        "publishedStrategyId": pub_id,
    })
    print(f"[5] subscribe status={status} localStrategyId={sub.get('localStrategyId','?')[:8]}...")
    assert status == 200 and sub.get("localStrategyId"), "订阅失败"

    # 6) 评分
    status, rating = _req("POST", "/api/paper/strategy-marketplace/rate", {
        "accountId": account_id,
        "publishedStrategyId": pub_id,
        "score": 5,
        "review": "非常好用",
    })
    print(f"[6] rate status={status} score={rating.get('score')}")
    assert status == 200 and rating.get("score") == 5

    # 7) 我的发布
    status, mine = _req("GET", f"/api/paper/strategy-marketplace/my-published?account_id={account_id}")
    print(f"[7] my-published status={status} count={len(mine) if isinstance(mine, list) else '?'}")
    assert status == 200 and len(mine) >= 1

    # 8) 排行榜
    status, lb = _req("GET", "/api/paper/strategy-marketplace/leaderboard?limit=10")
    print(f"[8] leaderboard status={status} count={len(lb) if isinstance(lb, list) else '?'}")
    assert status == 200 and len(lb) >= 1

    # 9) 下架
    status, un = _req("POST", f"/api/paper/strategy-marketplace/{pub_id}/unpublish?account_id={account_id}", {})
    print(f"[9] unpublish status={status} unpublished={un.get('unpublished')}")
    assert status == 200 and un.get("unpublished") is True

    print("\nALL STRATEGY MARKETPLACE SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
