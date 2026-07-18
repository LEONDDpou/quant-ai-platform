# 数据库设计（市场实时模块）

模块使用 **独立的异步 ORM 连接池**（`app/market/core/db.py` 中的 `async_engine` + `Base`），
与主线 SQLAlchemy 完全隔离。本地默认 `sqlite+aiosqlite:///./market.db`，生产指向
`postgresql+asyncpg://...`（由环境变量 `MARKET_DB_URL` 控制）。

启动时在 `app/main.py` 的 lifespan 中调用 `init_models()` 自动建表（`create_all`）。
所有表均带 `created_at` 时间戳，并对高频查询字段（`code` / `ts` / `period`）建索引，支撑百万级标的。

## 表清单

| 表名 | 用途 |
| --- | --- |
| `market_realtime_quote` | 实时行情快照（按 code+ts 多版本留存，可回放） |
| `market_kline` | 多周期 K 线（分时/1m/5m/15m/30m/日/周/月） |
| `market_capital_flow` | 实时资金流（主力/超大/大/中/小单 + 北向） |
| `market_breadth` | 市场宽度快照（涨跌家数 / 涨跌停） |
| `market_trade_signal` | 交易信号（策略/规则产生，供 AI 量化接口消费） |
| `market_strategy_result` | 策略回测/运行结果 |
| `market_ai_score` | AI 选股评分（综合分 + 多维分项 + 风险等级） |

## 核心表结构

### market_realtime_quote
| 列 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER PK | 自增 |
| code | VARCHAR(16) | 6 位 A 股代码 |
| name | VARCHAR(32) | 名称 |
| price / change / change_pct | FLOAT | 现价 / 涨跌额 / 涨跌幅% |
| volume | BIGINT | 成交量（手） |
| amount | FLOAT | 成交额（元） |
| turnover | FLOAT | 换手率% |
| pe / pb | FLOAT | 估值 |
| total_mv / float_mv | FLOAT | 总市值 / 流通市值（元） |
| source | VARCHAR(16) | 数据来源 |
| ts / created_at | DATETIME | 行情时间 / 写入时间 |

索引：`ix_rt_quote_code_ts(code, ts)`、`ix_rt_quote_ts(ts)`。

### market_kline
| 列 | 类型 | 说明 |
| --- | --- | --- |
| code | VARCHAR(16) | 标的 |
| period | VARCHAR(8) | minute/5min/.../day/week/month |
| dt | DATETIME | K 线时间 |
| open / high / low / close | FLOAT | OHLC |
| volume | BIGINT | 成交量 |
| amount | FLOAT | 成交额 |

唯一约束：`uq_kline_code_period_dt(code, period, dt)`；索引：`ix_kline_code_period(code, period)`。

### market_capital_flow
| 列 | 类型 | 说明 |
| --- | --- | --- |
| code | VARCHAR(16) | 标的 |
| name | VARCHAR(32) | 名称 |
| main_in | FLOAT | 主力净流入（元） |
| ultra_large / large / medium / small | FLOAT | 超大/大/中/小单净流入 |
| northbound | FLOAT | 北向资金（元，个股维度可能为空） |

索引：`ix_cf_code_ts(code, ts)`。

### market_breadth
| 列 | 类型 | 说明 |
| --- | --- | --- |
| trade_date | VARCHAR(10) | YYYY-MM-DD |
| total / up / down / flat | INTEGER | 总数 / 上涨 / 下跌 / 平盘 |
| limit_up / limit_down | INTEGER | 涨停 / 跌停 |
| northbound | FLOAT | 北向资金（全市场） |

索引：`ix_breadth_date(trade_date)`。

### market_ai_score
| 列 | 类型 | 说明 |
| --- | --- | --- |
| code / name | VARCHAR | 标的 |
| score | FLOAT | 综合评分 [0,100] |
| tech_score / fund_score / sentiment_score | FLOAT | 技术 / 资金 / 情绪分项 |
| momentum / volatility | FLOAT | 动量 / 波动率因子 |
| risk_level | VARCHAR(8) | low / mid / high |

索引：`ix_ai_code_ts(code, ts)`。

> 落库为 **best-effort**：`services/persistence.py` 中的 `save_*` 失败仅记录 warning，不影响实时推送主链路。
> 表结构由 ORM 模型（`core/models.py`）单一来源定义，无需手工建表。
