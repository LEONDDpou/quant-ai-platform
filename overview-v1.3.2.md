# v1.3.2 — 网站响应优化

## 问题
`/api/market-dynamics/a-share` 单次响应 12.8 秒，导致页面长时间白屏。

## 根因
`get_all_dynamics()` 中 8 个子函数**串行执行**，每个调用 westock-data CLI 2-5s，累积耗时巨大。

## 优化措施

### 后端（核心）
| 优化项 | 方案 | 效果 |
|--------|------|------|
| `get_all_dynamics()` | ThreadPoolExecutor(8) 全并行 | 总耗时 = max(子模块) 而非 sum |
| `get_market_indices()` | 批量 quote 一次替代 8 次串行 | 8×1.5s → 1.5s |
| `get_market_breadth()` | 并行 sh/sz | 2×3s → 3s |
| `get_stock_rankings()` | 复用一次 hot 替代两次 | 减少一次 CLI 调用 |
| CLI 超时 | 25s → 12-15s | 快速失败 |
| 缓存策略 | 新增 serve_stale 模式，后台刷新 | 热缓存 0.01s |

### 前端
| 优化项 | 方案 |
|--------|------|
| 骨架屏 | 新增 Skeleton/SkeletonCard/SkeletonTicker 组件 |
| 无阻塞刷新 | 刷新时保留旧数据，不闪烁 |
| 页面首次渲染 | 骨架屏立即显示代替全屏 spinner |

## 效果对比

| 端点 | 优化前 | 冷缓存 | 热缓存 |
|------|--------|--------|--------|
| `/api/market-dynamics/a-share` | 12.8s | 2.0s | 0.01s |
| `/api/institution/aggregate` | 0.85s | 0.85s | 0.01s |

## 构建验证
- TypeScript tsc: ✅ 零错误
- Next.js build: ✅ 16 routes 通过
- 生产构建: ✅ 静态页面生成成功
