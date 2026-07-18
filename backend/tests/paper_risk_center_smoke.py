"""模拟盘交易系统 — 智能风控中心集成冒烟测试（urllib 直连 :8000，无 pytest）。

流程：取/建账户 → 配置 → 指标 → 建规则 → 取规则 → 报告 → 扫描 → 全部已读。
运行：先确保后端已启动（python -m uvicorn app.main:app --port 8000），再执行本脚本。
"""
import json
import urllib.request
import sys

BASE = "http://127.0.0.1:8000"


def _req(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"}, method=method,
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main():
    # 1) 取账户（demo），无则创建
    status, accounts = _req("GET", "/api/paper/account?username=demo")
    assert status == 200, f"GET accounts failed: {status}"
    if accounts:
        aid = accounts[0]["id"]
    else:
        status, acc = _req("POST", "/api/paper/account", {
            "name": "风控冒烟账户", "initialCapital": 1000000, "username": "demo",
        })
        assert status == 200, f"create account failed: {status}"
        aid = acc["id"]
    print(f"[ok] account id={aid}")

    # 2) 配置风控阈值
    status, _ = _req("PUT", f"/api/paper/risk/{aid}/config", {
        "enabled": True, "maxPositionRatio": 0.5, "maxTotalPositionRatio": 0.9,
        "maxSingleAmount": 500000, "maxDailyLoss": 50000, "stopLossRatio": 0.2, "allowShort": False,
    })
    assert status == 200, f"PUT config failed: {status}"
    print("[ok] PUT /config")

    # 3) 实时指标
    status, m = _req("GET", f"/api/paper/risk/{aid}/metrics")
    assert status == 200 and "overallStatus" in m, f"GET metrics failed: {status}"
    print(f"[ok] GET /metrics overallStatus={m['overallStatus']}")

    # 4) 新建规则（黑名单）
    status, rule = _req("POST", f"/api/paper/risk/{aid}/rules", {
        "name": "冒烟黑名单", "ruleType": "BLACKLIST",
        "detail": {"codes": ["600519"]}, "severity": "critical",
    })
    assert status == 200 and "id" in rule, f"POST rule failed: {status}"
    rid = rule["id"]
    print(f"[ok] POST /rules id={rid}")

    # 5) 取规则
    status, rules = _req("GET", f"/api/paper/risk/{aid}/rules")
    assert status == 200 and any(r["id"] == rid for r in rules), f"GET rules failed: {status}"
    print(f"[ok] GET /rules count={len(rules)}")

    # 6) 风险报告
    status, rep = _req("GET", f"/api/paper/risk/{aid}/report")
    assert status == 200 and "score" in rep, f"GET report failed: {status}"
    print(f"[ok] GET /report score={rep['score']} activeRules={rep['activeRules']}")

    # 7) 扫描
    status, sc = _req("POST", f"/api/paper/risk/{aid}/scan")
    assert status == 200 and "recorded" in sc, f"POST scan failed: {status}"
    print(f"[ok] POST /scan recorded={sc['recorded']}")

    # 8) 全部已读
    status, ack = _req("POST", f"/api/paper/risk/{aid}/events/ack-all")
    assert status == 200 and "acked" in ack, f"POST ack-all failed: {status}"
    print(f"[ok] POST /events/ack-all acked={ack['acked']}")

    print("\nALL RISK CENTER SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
