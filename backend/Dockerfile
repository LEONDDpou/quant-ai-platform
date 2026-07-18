# 后端镜像 — FastAPI + westock 数据脚本 (Node)
FROM python:3.13-slim

# 系统依赖：
#   - nodejs   : 运行打包进镜像的 westock 取数脚本（需 >= 18）
#   - gcc/g++  : 部分 Python 包（numpy/scipy/akshare 等）源码构建时需要
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 打包的 westock 单文件脚本（零外部依赖）
COPY westock/ ./westock/
COPY app/ ./app/
COPY run.py .

# 运行时环境变量（docker-compose / .env 可覆盖）
ENV WESTOCK_SCRIPT=/app/westock/index.js \
    NODE_BIN=/usr/bin/node \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# 容器内固定单进程，确保 market_feed_loop 实时推送只跑一份（不启用 reload）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/openapi.json').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
