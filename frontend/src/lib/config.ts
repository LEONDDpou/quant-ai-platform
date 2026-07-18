// 后端 API 基地址 — 单一数据源，供所有前端模块复用。
// 部署时通过 NEXT_PUBLIC_API_BASE 配置（构建期注入）：
//   - 本地开发（前后端分离）：不设置 → 默认 http://localhost:8000
//   - Docker / 反向代理同域：设为 ""（空字符串）→ fetch("/api/...") 走相对路径
//
// 注意：必须用 `??` 而非 `||`，否则空字符串会被当成 falsy 回退到 localhost。
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
