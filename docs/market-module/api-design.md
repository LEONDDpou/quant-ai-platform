# API 接口设计（市场实时模块）

所有 REST 接口挂载于 `/api/market` 前缀，WebSocket 端点为 `/ws/market/realtime`。
统一响应为 JSON；错误以 HTTP 状态码 + `detail` 字段返回（FastAPI 默认）。

## 1. 实时行情聚合（AI 量化接口）— 需求 5

`GET /api/market/realtime?codes=600519,000858`

返回每只标的的 **实时行情 + 资金流 + 技术指标 + AI 评分**，是 AI 量化策略的核心数据入口。

Query 参数：
- `codes`（必填，逗号分隔 6 位 A 股代码，如 `600519,000858`）

响应 `RealtimeResponse`：
```json
{
  "ts": "2026-07-18 16:31:37",
  "source": "tencent",
  "count": 2,
  "items": [
    {
      "quote": {
        "code": "600519", "name": "贵州茅台", "price": 1253.0,
        "change": -5.99, "changePct": -0.48,
        "volume": 58417, "amount": 732273.0, "turnover": 0.47,
        "pe": 18.94, "pb": 0.0,
        "totalMv": 1566352000000.0, "floatMv": 1566352000000.0,
        "source": "tencent"
      },
      "capitalFlow": {
        "code": "600519", "available": true,
        "mainIn": -843263686.0, "ultraLarge": -772844739.0,
        "large": -70418947.0, "medium": 843890569.0, "small": -626883.0,
        "mainNetFlow5d": 1246759279.0
      },
      "technicals": {
        "ma5": 1392.42, "ma10": 1375.901, "ma20": 1343.01,
        "rsi14": 69.92, "macd": 33.953, "macdSignal": 31.86, "macdHist": 4.184
      },
      "aiScore": {
        "score": 48.3, "techScore": 43.2, "fundScore": 50.0,
        "sentimentScore": 47.6, "momentum": -0.048, "volatility": 0.0,
        "riskLevel": "low"
      }
    }
  ]
}
```

## 2. 单只实时行情

`GET /api/market/quote/{code}` → `QuoteOut`

## 3. 多周期 K 线 — 需求 2

`GET /api/market/kline?code=600519&period=day&limit=120`

- `period`：`1m` / `5m` / `15m` / `30m` / `day` / `week` / `month` / `intraday`
- `limit`：1–800（默认 120）

响应：`KlineBarOut[]`，字段 `dt, open, high, low, close, volume, amount`。

## 4. 资金流 — 需求 3

`GET /api/market/capital-flow?codes=600519`

- `codes` 为空时返回北向资金（全市场口径）+ 龙虎榜。

响应：
```json
{
  "items": [ { "code": "600519", "available": true, "mainIn": -8.4e8, ... } ],
  "northbound": -123456789.0,
  "lhb": [ { "code": "...", "name": "...", "rank": 1, ... } ]
}
```

## 5. 市场监控 — 需求 4

`GET /api/market/monitor` →
```json
{
  "breadth": { "total": 4992, "upCount": 386, "downCount": 4571,
               "flatCount": 35, "limitUp": 32, "limitDown": 206, "breadthPct": 7.7 },
  "rankings": { "topGainers": [...], "topLosers": [...], "topVolume": [...] },
  "hotStocks": [ { "code": "...", "name": "...", "changePct": 9.9, "price": 12.3, "type": "..." } ],
  "sectorRankings": [ { "code": "...", "name": "...", "chg5d": 3.2, "chg20d": 5.1, "chg60d": 8.8, "chg120d": 12.4, "chg250d": 20.1 } ]
}
```

## 6. 数据源健康（故障切换状态）— 需求 8

`GET /api/market/sources` → `SourceHealth[]`
```json
[
  { "name": "tencent", "available": true, "circuit": "closed", "lastUsed": true },
  { "name": "eastmoney", "available": true, "circuit": "closed", "lastUsed": false },
  { "name": "sina", "available": true, "circuit": "closed", "lastUsed": false },
  { "name": "akshare", "available": true, "circuit": "closed", "lastUsed": false }
]
```
`circuit` 取值：`closed`（正常）/ `open`（熔断中）/ `half_open`（探测中）。

## 7. WebSocket 实时推送 — 需求 7

`WS /ws/market/realtime`

连接即推一帧快照，之后按 `MARKET_REFRESH_RATE`（默认 3s）周期广播关注池行情。
消息格式：
```json
{
  "type": "market_realtime",
  "ts": "2026-07-18 16:31:40",
  "source": "tencent",
  "quotes": [
    { "code": "600519", "name": "贵州茅台", "price": 1253.0, "change": -5.99,
      "change_pct": -0.48, "volume": 58417, "amount": 732273.0, "turnover": 0.47,
      "pe": 18.94, "pb": 0.0, "total_mv": 1566352000000.0, "float_mv": 1566352000000.0,
      "open": 1260.0, "high": 1265.0, "low": 1250.0, "prev_close": 1258.99,
      "source": "tencent", "ts": 1752832300.0 }
  ]
}
```

> 前端 `useMarketRealtimeSocket` 订阅该端点，用于实时价格刷新；完整快照（技术指标 / AI 评分 / 资金流）仍由 REST `/api/market/realtime` 拉取，两者互补。
