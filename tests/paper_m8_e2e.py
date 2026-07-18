"""M8 回测模块 — 端到端验证（urllib 直连运行中的后端，无需 httpx）。

覆盖：
- /strategies 可选策略列表
- POST /run 运行回测（落库 + 导出三标准产物 + HTML 仪表盘）
- GET /runs 历史列表、GET /runs/{id} 详情
- GET /runs/{id}/file/{name} 下载产物（含白名单防护）
- 断言：权益曲线非空、指标为数值、数据源标识正确、产物文件非空
"""
import json
import urllib.error
import urllib.request

BASE = "http://localhost:8000/api/paper/backtest"


def req(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def main():
    # 1) 策略列表
    st, opts = req("GET", "/strategies")
    assert st == 200, (st, opts)
    assert len(opts) >= 1, "策略列表为空"
    print("策略列表:", [o["label"] for o in opts])

    # 2) 运行回测（默认均线交叉 + 沪深300 池）
    st, run1 = req(
        "POST",
        "/run",
        {"strategy": "均线交叉(MA5/MA20)", "stockPool": "沪深300", "initialCapital": 1_000_000},
    )
    assert st == 200, (st, run1)
    assert run1["id"] > 0
    assert len(run1["equityCurve"]) > 0, "权益曲线为空"
    assert isinstance(run1["totalReturn"], (int, float))
    assert run1["dataSource"] in ("westock", "mock")
    print(
        "run1 #%d | 总收益 %.2f%% | 年化 %.2f%% | 夏普 %.2f | 回撤 %.2f%% | 胜率 %.1f%% | 交易 %d | 数据源 %s | 权益点 %d"
        % (
            run1["id"],
            run1["totalReturn"],
            run1["annualizedReturn"],
            run1["sharpeRatio"],
            run1["maxDrawdown"],
            run1["winRate"],
            run1["totalTrades"],
            run1["dataSource"],
            len(run1["equityCurve"]),
        )
    )

    # 3) 因子择时策略 + 指定标的
    st, run2 = req("POST", "/run", {"strategy": "ICU均线", "code": "600519", "initialCapital": 500_000})
    assert st == 200, (st, run2)
    print("run2 #%d | 标的 %s | 数据源 %s" % (run2["id"], run2["symbol"], run2["dataSource"]))

    # 4) 历史列表
    st, runs = req("GET", "/runs?limit=10")
    assert st == 200, (st, runs)
    assert len(runs) >= 2, "历史列表不足"
    print("历史回测条数:", len(runs))

    # 5) 详情
    st, det = req("GET", "/runs/%d" % run1["id"])
    assert st == 200, (st, det)
    assert det["id"] == run1["id"]

    # 6) 下载产物（三标准文件 + HTML 仪表盘）
    for fn in ("index.html", "equity.csv", "trades.csv", "summary.json"):
        url = "%s/runs/%d/file/%s" % (BASE, run1["id"], fn)
        with urllib.request.urlopen(url, timeout=30) as resp:
            content = resp.read()
        assert len(content) > 0, "%s 内容为空" % fn
        print("产物下载 OK:", fn, len(content), "bytes")

    # 7) 白名单防护
    st, _ = req("GET", "/runs/%d/file/secret.txt" % run1["id"])
    assert st == 400, st
    print("非法文件名拦截 OK (400)")

    print("\n✅ M8 回测模块 E2E 全部通过")


if __name__ == "__main__":
    main()
