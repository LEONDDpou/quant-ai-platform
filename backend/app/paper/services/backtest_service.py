"""模拟盘交易系统 — M8 回测服务。

职责：
- 包装主平台已验证的 ``backtest_engine.run_backtest``（均线交叉 / 因子择时，
  严格防未来函数、A股 T+1 友好），把一次策略回测落库到 ``backtest_runs``；
- 修正数据源标识（引擎硬编码 westock，这里按真实可用性回写为 westock / mock）；
- 按 StrategyBacktestExpert 约定，导出三标准产物 + 独立 HTML 仪表盘到
  ``backtest_results/<run_id>/``（equity.csv / trades.csv / summary.json / index.html），
  供前端一键下载离线查看；
- 提供历史列表 / 详情 / 可选策略列表。

注：回测结果仅为模型输出，不构成投资建议。
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.paper.domain_models import BacktestRun
from app.paper.errors import PaperError
from app.paper.repositories.backtest_repo import BacktestRepository
from app.paper.schemas import (
    BacktestEventStrategy,
    BacktestRunResponse,
    BacktestStrategyOption,
    RunBacktestRequest,
    RunEventBacktestRequest,
)
from app.services import backtest_engine
from app.services import event_backtest_engine
from app.services import data_provider as dp

# 回测产物根目录：quant-ai-platform/backtest_results
BACKTEST_RESULTS_DIR = Path(__file__).resolve().parents[4] / "backtest_results"

# 可选策略（与 backtest_engine 的因子关键词对齐）
STRATEGY_OPTIONS: List[BacktestStrategyOption] = [
    BacktestStrategyOption(key="均线交叉(MA5/MA20)", label="均线交叉 (MA5/MA20)"),
    BacktestStrategyOption(key="ICU均线", label="ICU 均线择时"),
    BacktestStrategyOption(key="动量因子", label="动量因子 (20日)"),
    BacktestStrategyOption(key="反转因子", label="反转因子 (5日)"),
    BacktestStrategyOption(key="特质波动率", label="低特质波动率 regime"),
    BacktestStrategyOption(key="均线收敛", label="均线收敛 (MA5/MA60)"),
]

# 事件驱动策略模板（M181；前端下拉 + 规则预设）
EVENT_STRATEGY_TEMPLATES: List[BacktestEventStrategy] = [
    BacktestEventStrategy(
        key="双均线金叉死叉",
        label="双均线金叉/死叉",
        rules=[
            {"side": "entry", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
            {"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
        ],
        risk={"stopLoss": 8.0, "takeProfit": 0.0},
    ),
    BacktestEventStrategy(
        key="突破跟随",
        label="N日突破跟随",
        rules=[
            {"side": "entry", "kind": "price_breakout", "params": {"window": 20}},
            {"side": "exit", "kind": "ma_cross", "params": {"fast": 5, "slow": 20}},
        ],
        risk={"stopLoss": 10.0, "takeProfit": 30.0},
    ),
    BacktestEventStrategy(
        key="RSI反转",
        label="RSI 超卖反转",
        rules=[
            {"side": "entry", "kind": "rsi", "params": {"period": 14, "threshold": 30}},
            {"side": "exit", "kind": "rsi", "params": {"period": 14, "threshold": 30}},
        ],
        risk={"stopLoss": 6.0, "takeProfit": 20.0},
    ),
    BacktestEventStrategy(
        key="均线+止损止盈",
        label="均线 + 止损止盈",
        rules=[
            {"side": "entry", "kind": "ma_cross", "params": {"fast": 10, "slow": 60}},
            {"side": "exit", "kind": "ma_cross", "params": {"fast": 10, "slow": 60}},
        ],
        risk={"stopLoss": 8.0, "takeProfit": 25.0},
    ),
]


def _real_data_source(symbol: str) -> str:
    """按该标的真实 K线 是否可取，回写数据源。

    注意：``is_available()`` 仅检查脚本/Node 存在，不反映真实连通性；
    沙箱内 westock 脚本存在但外网受限时会静默回退 mock。这里直接探测该标的的
    真实 K线 拉取（绕过 mock 兜底），失败即记为 mock，保证数据源标识诚实。
    """
    try:
        from app.services import westock_client

        if not westock_client.is_available():
            return "mock"
        ws_code = dp.to_westock_code(symbol or "sh000300")
        rows = westock_client.run_table(
            ["kline", ws_code, "--period", "day", "--limit", "5", "--fq", "qfq"],
            timeout=15,
        )
        return "westock" if rows else "mock"
    except Exception:
        return "mock"


def _to_response(run: BacktestRun) -> BacktestRunResponse:
    return BacktestRunResponse(
        id=run.id,
        accountId=run.account_id,
        strategyName=run.strategy_name or "",
        symbol=run.symbol or "",
        startDate=run.start_date or "",
        endDate=run.end_date or "",
        initialCapital=run.initial_capital or 0.0,
        totalReturn=run.total_return or 0.0,
        annualizedReturn=run.annualized_return or 0.0,
        sharpeRatio=run.sharpe_ratio or 0.0,
        maxDrawdown=run.max_drawdown or 0.0,
        calmarRatio=run.calmar_ratio or 0.0,
        alpha=run.alpha or 0.0,
        beta=run.beta or 0.0,
        winRate=run.win_rate or 0.0,
        totalTrades=run.total_trades or 0,
        equityCurve=run.equity_curve or [],
        trades=run.trades or [],
        dataSource=run.data_source or "",
        params=run.params or {},
        mode=run.mode or "factor",
        createdAt=run.created_at.isoformat() if run.created_at else "",
    )


class BacktestService:
    """回测服务：运行 / 历史 / 详情 / 策略列表。"""

    def __init__(self):
        self.repo = BacktestRepository()

    # ── 公开接口 ──
    def strategy_options(self) -> List[BacktestStrategyOption]:
        return STRATEGY_OPTIONS

    def event_strategy_templates(self) -> List[BacktestEventStrategy]:
        """事件驱动策略模板（前端下拉 + 规则预设）。"""
        return EVENT_STRATEGY_TEMPLATES

    def run(self, req: RunBacktestRequest) -> BacktestRunResponse:
        """运行一次回测（因子/均线）并落库 + 导出产物。"""
        try:
            result = backtest_engine.run_backtest(
                strategy=req.strategy,
                startDate=req.startDate,
                endDate=req.endDate,
                stockPool=req.stockPool,
                initialCapital=req.initialCapital,
                code=req.code,
            )
        except Exception as e:  # noqa: BLE001
            raise PaperError(f"回测执行失败：{e}")

        # 修正数据源（引擎硬编码 westock，这里按该标的真实连通性回写）
        result["dataSource"] = _real_data_source(result.get("symbol", ""))

        # 派生 Calmar（年化/最大回撤，均为 %；无基准则 alpha/beta 留 0）
        ann = float(result.get("annualizedReturn", 0.0) or 0.0)
        mdd = float(result.get("maxDrawdown", 0.0) or 0.0)
        calmar = round(ann / mdd, 2) if mdd > 0 else 0.0

        params = {
            "strategy": req.strategy,
            "stockPool": req.stockPool,
            "code": req.code,
            "startDate": req.startDate,
            "endDate": req.endDate,
            "initialCapital": req.initialCapital,
            "accountId": req.accountId,
            "strategyId": req.strategyId,
        }

        run = BacktestRun(
            account_id=req.accountId,
            strategy_name=req.strategy,
            symbol=result.get("symbol", ""),
            start_date=result.get("startDate", ""),
            end_date=result.get("endDate", ""),
            initial_capital=req.initialCapital,
            total_return=float(result.get("totalReturn", 0.0) or 0.0),
            annualized_return=float(result.get("annualizedReturn", 0.0) or 0.0),
            sharpe_ratio=float(result.get("sharpeRatio", 0.0) or 0.0),
            max_drawdown=float(result.get("maxDrawdown", 0.0) or 0.0),
            calmar_ratio=calmar,
            alpha=0.0,
            beta=0.0,
            win_rate=float(result.get("winRate", 0.0) or 0.0),
            total_trades=int(result.get("totalTrades", 0) or 0),
            equity_curve=result.get("equityCurve", []),
            trades=result.get("trades", []),
            data_source=result.get("dataSource", "mock"),
            params=params,
            mode="factor",
        )
        self.repo.save(run)

        # 导出三标准产物 + HTML 仪表盘
        try:
            self._export_run(run, result)
        except Exception as e:  # 导出失败不应影响已落库的结果
            print(f"[backtest] 产物导出失败（已落库）：{e}")

        return _to_response(run)

    # ── 事件驱动回测（M181）──
    def run_event(self, req: RunEventBacktestRequest) -> BacktestRunResponse:
        """运行一次事件驱动回测（多标的等权组合）并落库 + 导出产物。"""
        # 1) 解析标的宇宙：优先 universe，其次单标的 code，再次股票池映射
        universe = list(req.universe or [])
        if not universe and req.code:
            universe = [req.code]
        if not universe and req.stockPool:
            universe = [backtest_engine.POOL_MAP.get(req.stockPool, "sh000300")]
        if not universe:
            raise PaperError("事件驱动回测需要至少一个标的（universe / code / stockPool）")

        # 2) 拉取每个标的的真实 K线（westock，失败静默回退 mock）
        series_map: dict = {}
        names_map: dict = {}
        for code in universe:
            try:
                kline = dp.get_stock_kline(code, period="day", limit=700)
                if kline:
                    series_map[code] = kline
                    names_map[code] = code
            except Exception:
                continue
        if not series_map:
            raise PaperError("无法获取任何标的的 K线 数据，事件驱动回测中止")

        # 3) 调用纯函数引擎
        try:
            result = event_backtest_engine.run_event_backtest(
                rules=req.rules,
                universe=list(series_map.keys()),
                startDate=req.startDate,
                endDate=req.endDate,
                initialCapital=req.initialCapital,
                risk=req.risk or {},
                strategyName=req.strategyName or "事件驱动组合",
                series_map=series_map,
                names_map=names_map,
            )
        except Exception as e:  # noqa: BLE001
            raise PaperError(f"事件驱动回测执行失败：{e}")

        # 4) 数据源：只要有任一标的取到真实 K线 即记为 westock，否则 mock
        result["dataSource"] = _real_data_source(list(series_map.keys())[0])

        # 5) 派生 Calmar
        ann = float(result.get("annualizedReturn", 0.0) or 0.0)
        mdd = float(result.get("maxDrawdown", 0.0) or 0.0)
        calmar = round(ann / mdd, 2) if mdd > 0 else 0.0

        params = {
            "strategyName": req.strategyName,
            "universe": req.universe,
            "stockPool": req.stockPool,
            "code": req.code,
            "startDate": req.startDate,
            "endDate": req.endDate,
            "initialCapital": req.initialCapital,
            "rules": req.rules,
            "risk": req.risk,
            "accountId": req.accountId,
            "strategyId": req.strategyId,
        }

        run = BacktestRun(
            account_id=req.accountId,
            strategy_name=req.strategyName or "事件驱动组合",
            symbol=result.get("symbol", ""),
            start_date=result.get("startDate", ""),
            end_date=result.get("endDate", ""),
            initial_capital=req.initialCapital,
            total_return=float(result.get("totalReturn", 0.0) or 0.0),
            annualized_return=float(result.get("annualizedReturn", 0.0) or 0.0),
            sharpe_ratio=float(result.get("sharpeRatio", 0.0) or 0.0),
            max_drawdown=float(result.get("maxDrawdown", 0.0) or 0.0),
            calmar_ratio=calmar,
            alpha=0.0,
            beta=0.0,
            win_rate=float(result.get("winRate", 0.0) or 0.0),
            total_trades=int(result.get("totalTrades", 0) or 0),
            equity_curve=result.get("equityCurve", []),
            trades=result.get("trades", []),
            data_source=result.get("dataSource", "mock"),
            params=params,
            mode="event",
        )
        self.repo.save(run)

        try:
            self._export_run(run, result)
        except Exception as e:  # 导出失败不应影响已落库的结果
            print(f"[backtest] 事件回测产物导出失败（已落库）：{e}")

        return _to_response(run)

    def list_runs(
        self, account_id: Optional[int] = None, limit: int = 50
    ) -> List[BacktestRunResponse]:
        runs = self.repo.list_runs(account_id=account_id, limit=limit)
        return [_to_response(r) for r in runs]

    def get(self, run_id: int) -> BacktestRunResponse:
        run = self.repo.get(run_id)
        if not run:
            raise PaperError(f"回测记录不存在: #{run_id}")
        return _to_response(run)

    # ── 产物导出（StrategyBacktestExpert 约定）──
    def _export_run(self, run: BacktestRun, result: dict) -> None:
        out_dir = BACKTEST_RESULTS_DIR / str(run.id)
        os.makedirs(out_dir, exist_ok=True)

        # 1) equity.csv
        with open(out_dir / "equity.csv", "w", encoding="utf-8") as f:
            f.write("date,value\n")
            for p in result.get("equityCurve", []):
                f.write(f"{p.get('date','')},{p.get('value',0)}\n")

        # 2) trades.csv（按全部出现过的字段写表头）
        trades = result.get("trades", [])
        if trades:
            keys = []
            for t in trades:
                for k in t.keys():
                    if k not in keys:
                        keys.append(k)
            with open(out_dir / "trades.csv", "w", encoding="utf-8") as f:
                f.write(",".join(keys) + "\n")
                for t in trades:
                    f.write(",".join(str(t.get(k, "")) for k in keys) + "\n")

        # 3) summary.json
        summary = {
            "runId": run.id,
            "strategy": run.strategy_name,
            "symbol": run.symbol,
            "startDate": run.start_date,
            "endDate": run.end_date,
            "initialCapital": run.initial_capital,
            "totalReturn": run.total_return,
            "annualizedReturn": run.annualized_return,
            "sharpeRatio": run.sharpe_ratio,
            "maxDrawdown": run.max_drawdown,
            "calmarRatio": run.calmar_ratio,
            "alpha": run.alpha,
            "beta": run.beta,
            "winRate": run.win_rate,
            "totalTrades": run.total_trades,
            "dataSource": run.data_source,
            "params": run.params,
            "createdAt": run.created_at.isoformat() if run.created_at else "",
        }
        with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 4) index.html 仪表盘
        html = _render_dashboard_html(run, result)
        with open(out_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(html)


def _render_dashboard_html(run: BacktestRun, result: dict) -> str:
    """生成自包含 HTML 仪表盘（中文；ECharts 通过 CDN 渲染权益曲线）。"""
    equity = result.get("equityCurve", [])
    trades = result.get("trades", [])
    ds_label = "真实行情 (westock)" if run.data_source == "westock" else "模拟数据 (mock)"
    created = run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else ""

    # 交易明细表
    trade_rows = ""
    for t in trades:
        pnl = t.get("pnl")
        pnl_str = f"{pnl:,.2f}" if isinstance(pnl, (int, float)) else "-"
        trade_rows += (
            f"<tr><td>{t.get('date','')}</td><td>{t.get('code','')}</td>"
            f"<td>{'买入' if t.get('action')=='buy' else '卖出'}</td>"
            f"<td>{t.get('price',0):,.2f}</td><td>{t.get('shares',0):,}</td>"
            f"<td>{t.get('amount',0):,.0f}</td><td>{pnl_str}</td></tr>"
        )
    if not trade_rows:
        trade_rows = '<tr><td colspan="7" class="muted">本区间无完整买卖回合</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>回测报告 · {run.strategy_name}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f1420;color:#e2e8f0;margin:0;padding:24px;}}
  h1{{font-size:20px;margin:0 0 4px;}}
  .sub{{color:#64748b;font-size:12px;margin-bottom:20px;}}
  .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px;}}
  .kpi{{background:#1a2030;border:1px solid #232b3d;border-radius:10px;padding:14px;}}
  .kpi .k{{font-size:11px;color:#64748b;}}
  .kpi .v{{font-size:20px;font-weight:700;margin-top:4px;}}
  .pos{{color:#34d399;}} .neg{{color:#f87171;}}
  .card{{background:#1a2030;border:1px solid #232b3d;border-radius:10px;padding:16px;margin-bottom:20px;}}
  .card h2{{font-size:14px;margin:0 0 12px;}}
  table{{width:100%;border-collapse:collapse;font-size:12px;}}
  th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #232b3d;}}
  th{{color:#64748b;font-weight:600;}}
  .muted{{color:#64748b;}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;background:#334155;color:#cbd5e1;}}
  .disc{{color:#64748b;font-size:11px;margin-top:24px;line-height:1.6;}}
</style>
</head>
<body>
  <h1>回测报告 · {run.strategy_name}</h1>
  <div class="sub">标的 {run.symbol} · 区间 {run.start_date} ~ {run.end_date} · 初始资金 ¥{run.initial_capital:,.0f} · 数据源 <span class="badge">{ds_label}</span> · 生成于 {created}</div>

  <div class="kpis">
    <div class="kpi"><div class="k">总收益率</div><div class="v {'pos' if run.total_return>=0 else 'neg'}">{run.total_return:+.2f}%</div></div>
    <div class="kpi"><div class="k">年化收益率</div><div class="v {'pos' if run.annualized_return>=0 else 'neg'}">{run.annualized_return:+.2f}%</div></div>
    <div class="kpi"><div class="k">夏普比率</div><div class="v">{run.sharpe_ratio:.2f}</div></div>
    <div class="kpi"><div class="k">最大回撤</div><div class="v neg">{run.max_drawdown:.2f}%</div></div>
    <div class="kpi"><div class="k">Calmar</div><div class="v">{run.calmar_ratio:.2f}</div></div>
    <div class="kpi"><div class="k">胜率</div><div class="v">{run.win_rate:.1f}%</div></div>
    <div class="kpi"><div class="k">交易次数</div><div class="v">{run.total_trades}</div></div>
  </div>

  <div class="card">
    <h2>权益曲线</h2>
    <div id="equity" style="height:360px;"></div>
  </div>

  <div class="card">
    <h2>交易明细</h2>
    <table><thead><tr><th>日期</th><th>代码</th><th>方向</th><th>价格</th><th>股数</th><th>金额</th><th>盈亏</th></tr></thead>
    <tbody>{trade_rows}</tbody></table>
  </div>

  <div class="disc">⚠️ 以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。投资有风险，决策需谨慎。</div>

<script>
  var chart = echarts.init(document.getElementById('equity'));
  var data = {json.dumps(equity, ensure_ascii=False)};
  chart.setOption({{
    backgroundColor:'transparent',
    grid:{{top:20,right:20,bottom:30,left:64}},
    tooltip:{{trigger:'axis'}},
    xAxis:{{type:'category',data:data.map(function(d){{return d.date;}}),axisLine:{{lineStyle:{{color:'#2a3142'}}}},axisLabel:{{color:'#64748b',fontSize:10}}}},
    yAxis:{{type:'value',axisLine:{{show:false}},splitLine:{{lineStyle:{{color:'#1a1f2e'}}}},axisLabel:{{color:'#64748b',fontSize:10}}}},
    series:[{{type:'line',data:data.map(function(d){{return d.value;}}),smooth:true,symbol:'none',lineStyle:{{color:'#3b82f6',width:2}},areaStyle:{{color:'rgba(59,130,246,0.15)'}}}}]
  }});
  window.addEventListener('resize', function(){{ chart.resize(); }});
</script>
</body>
</html>"""
