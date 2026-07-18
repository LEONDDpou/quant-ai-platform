# 部署指南（Deployment Guide）

本平台已完成「可部署形态」改造：所有本地硬编码已被抽离为环境变量，数据层
（westock 取数脚本）已打包进仓库，并提供了完整的 Docker 编排。

---

## 一、环境变量清单

### 后端（FastAPI）
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./quant.db` | 生产改为 `postgresql+psycopg://user:pass@host:5432/quantdb` |
| `WESTOCK_SCRIPT` | `backend/westock/index.js`（仓库内） | westock 取数脚本路径，容器内固定为 `/app/westock/index.js` |
| `NODE_BIN` | 自动探测 `/usr/bin/node`、`/usr/local/bin/node` 等 | Node 可执行文件 |
| `CORS_ALLOW_ORIGINS` | `*` | 生产改为前端域名逗号分隔，如 `https://app.example.com` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | — | AI 研究员大模型配置 |
| `LLM_TIMEOUT` / `LLM_MAX_TOKENS` | `60` / `1500` | LLM 调用参数 |
| `WS_PUSH_INTERVAL` | `5` | WebSocket 实时推送间隔（秒） |

### 前端（Next.js）
| 变量 | 构建期/运行期 | 说明 |
|------|------|------|
| `NEXT_PUBLIC_API_BASE` | 构建期注入 | 本地开发留空（默认 `http://localhost:8000`）；Docker/反向代理同域部署设为 `""`（走相对路径 `/api`、`/ws`） |

> ⚠️ `NEXT_PUBLIC_*` 是 **构建期** 变量，修改后必须重新 `npm run build`（或 `docker compose build frontend`）。

---

## 二、本地开发（未变）

```bash
# 后端
cd backend
/path/to/venv/python run.py            # http://localhost:8000

# 前端（另开终端）
cd frontend
npm install --legacy-peer-deps
npm run dev                            # http://localhost:3000
```

本地默认 `NEXT_PUBLIC_API_BASE` 为空 → 回退 `http://localhost:8000`，前后端分离照常工作。

---

## 三、Docker 全栈部署（推荐）

前置：服务器安装好 **Docker** 与 **Docker Compose v2**。

```bash
cd quant-ai-platform

# 1) 准备环境变量
cp .env.example .env
#   编辑 .env，至少填入 LLM_API_KEY

# 2) 构建并启动（含 Postgres + 后端 + 前端 + nginx 反向代理）
docker compose up -d --build

# 3) 访问
#   浏览器打开 http://<服务器IP>  (nginx 已把 /api、/ws 代理到后端)
```

编排结构：

```
            :80
   ┌──────────────────┐
   │   nginx (反向代理) │
   └──┬───────────┬────┘
      │ /api,/ws  │ /
      ▼           ▼
  backend:8000  frontend:3000
      │
  postgres:5432 (quantdb)
```

- 前端 `/` 与后端 `/api`、`/ws` 同域，无需 CORS（nginx 已处理）。
- 数据库默认用 compose 内的 Postgres（`quant_pgdata` 卷持久化）。
- `westock` 脚本随后端镜像打包，无需在服务器另行安装。

查看日志：`docker compose logs -f backend` / `frontend` / `nginx`
停止：`docker compose down`

---

## 四、仅部署前端（静态壳 / CloudStudio）

若只想把界面挂到公网、暂时不要后端数据：

```bash
cd frontend
npm install --legacy-peer-deps
npm run build
# 将 .next/standalone 或静态产物托管到 CloudStudio / 任意静态托管
```

> 注意：纯静态托管下所有图表/数据为空（无后端）。如需真实数据，请走第三节全栈部署。

---

## 五、生产加固建议

1. **数据库**：正式环境务必使用 Postgres（compose 已配置），并定期备份 `quant_pgdata` 卷。
2. **CORS**：`CORS_ALLOW_ORIGINS` 改为你的真实前端域名，不要长期保留 `*`。
3. **HTTPS**：在 nginx 前加一层 TLS（Let's Encrypt / 云厂商证书），或让云负载均衡终止 TLS。
4. **密钥**：`LLM_API_KEY` 等通过 `.env` 或编排平台 Secret 注入，勿提交进仓库（`.env` 已在 `.dockerignore` 排除）。
5. **数据接口外网**：腾讯行情接口需服务器能访问外网；若部署在受限内网，westock 取数会失败（后端会返回错误而非崩溃，页面降级显示）。
6. **资源**：`akshare` / `numpy` / `scipy` 等依赖较重，首次 `docker compose build` 可能耗时数分钟。
```
