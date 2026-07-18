# 前端镜像 — Next.js
FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

# 反向代理同域部署：NEXT_PUBLIC_API_BASE 置空 → 前端走相对路径 /api 与 /ws
# 注意：NEXT_PUBLIC_* 为构建期注入，改此值需重新 build。
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
