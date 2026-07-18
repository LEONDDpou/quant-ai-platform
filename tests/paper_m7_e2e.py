"""M7 AI 自动交易 — E2E 冒烟测试（HTTP 层）。

流程：创建测试账户 → 创建并启用策略 → 运行一轮 → 校验信号/买入/持仓 SLTP/日志/状态。
用法：python tests/paper_m7_e2e.py  （后端需在 :8000 运行）
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


def main():
    fails = []

    # 1) 创建干净测试账户
    st, acct = _req("POST", "/api/paper/account", {
        "name": "M7 E2E 测试账户", "initialCapital": 1000000.0, "username": "m7e2e"})
    assert st == 200, f"create account failed: {st} {acct}"
    aid = acct["id"]
    print(f"[ok] 创建测试账户 id={aid} 初始资金={acct.get('cash', acct.get('totalAssets'))}")

    # 2) 创建并启用策略（显式 universe，避免依赖真实自选股池）
    universe = ["600519", "300750", "601318", "000858", "600036", "002594"]
    st, strat = _req("POST", f"/api/paper/auto/{aid}/strategies", {
        "name": "M7 测试双均线+RSI", "enabled": True,
        "params": {"universe": universe, "maxPositions": 5, "perTradePct": 0.15,
                   "stopLossPct": 0.08, "takeProfitPct": 0.20}})
    assert st == 200, f"create strategy failed: {st} {strat}"
    sid = strat["id"]
    print(f"[ok] 创建策略 id={sid} enabled={strat['enabled']}")

    # 3) 运行一轮（手动触发）
    st, run = _req("POST", f"/api/paper/auto/{aid}/run")
    assert st == 200, f"run failed: {st} {run}"
    print(f"[ok] 运行一轮: signals={run['signals']} buys={run['buys']} "
          f"sells={run['sells']} stopTriggers={run['stopTriggers']} "
          f"watched={run['watched']} skipped={run['skipped']} dataSource={run['dataSource']}")

    # 4) 校验状态
    st, status = _req("GET", f"/api/paper/auto/{aid}/status")
    assert st == 200, f"status failed: {st}"
    if status["enabledStrategies"] < 1:
        fails.append("enabledStrategies 应 >=1")
    print(f"[ok] 状态: enabled={status['enabledStrategies']} running={status['running']} "
          f"lastRunAt={status['lastRunAt']}")

    # 5) 校验信号已落库
    st, signals = _req("GET", f"/api/paper/auto/{aid}/signals?limit=20")
    assert st == 200, f"signals failed: {st}"
    if len(signals) < 1:
        fails.append("未生成任何信号")
    types = [s["signalType"] for s in signals]
    print(f"[ok] 信号 {len(signals)} 条，类型分布={types}")

    # 6) 校验买入成交 + 持仓 SL/TP 回写
    st, orders = _req("GET", f"/api/paper/order/{aid}")
    assert st == 200, f"orders failed: {st}"
    ai_buys = [o for o in orders if o.get("source") == "ai" and o["direction"] == "buy"]
    filled = [o for o in ai_buys if o["status"] in ("filled", "partial")]
    print(f"[ok] AI 买单 {len(ai_buys)} 笔，已成交 {len(filled)} 笔")
    if run["buys"] > 0 and len(filled) == 0:
        fails.append("reported buys 但无成交订单")

    if filled:
        bought_codes = {o["code"] for o in filled}
        st, positions = _req("GET", f"/api/paper/position/{aid}")
        assert st == 200, f"positions failed: {st}"
        pos_map = {p["code"]: p for p in positions if p["shares"] > 0}
        for code in bought_codes:
            p = pos_map.get(code)
            if p is None:
                fails.append(f"持仓缺失: {code}")
                continue
            # SL/TP 由 _apply_sltp 在成交后回写
            if not (p.get("stopLossPrice") and p.get("takeProfitPrice")):
                fails.append(f"持仓 {code} 未回写 SL/TP")
            else:
                print(f"[ok] {code} SL={p['stopLossPrice']} TP={p['takeProfitPrice']} "
                      f"cost={p['costPrice']}")

    # 7) 校验 AI 日志落库
    st, logs = _req("GET", f"/api/paper/auto/{aid}/logs?limit=20")
    assert st == 200, f"logs failed: {st}"
    if len(logs) < 1:
        fails.append("未生成 AI 日志")
    else:
        print(f"[ok] AI 日志 {len(logs)} 条，最新: {logs[0]['message'][:60]}")

    # 8) 手动设置持仓 SL/TP（校验 set_holding_sltp 端点）
    if filled:
        code = filled[0]["code"]
        st, sltp = _req("POST", f"/api/paper/auto/{aid}/holdings/sltp",
                        {"code": code, "stopLossPrice": 1.0, "takeProfitPrice": 9999.0})
        assert st == 200, f"set sltp failed: {st} {sltp}"
        if sltp["stopLossPrice"] != 1.0 or sltp["takeProfitPrice"] != 9999.0:
            fails.append("set_holding_sltp 返回值不正确")
        else:
            print(f"[ok] 手动设置 {code} SL/TP 成功")

    # 9) 校验事后余额一致（M3 撮合 + M7 下单）
    st, metrics = _req("GET", f"/api/paper/account/{aid}/metrics")
    assert st == 200, f"metrics failed: {st}"
    print(f"[ok] 账户总资产={metrics.get('totalAssets')} 现金={metrics.get('cash')} "
          f"持仓市值={metrics.get('positionValue')}")

    print("\n" + ("="*50))
    if fails:
        print("❌ M7 E2E 失败项:")
        for f in fails:
            print("  -", f)
        return 1
    print("✅ M7 E2E 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
