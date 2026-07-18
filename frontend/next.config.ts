import type { NextConfig } from "next";

// STATIC_EXPORT=1 时启用静态导出（用于 CloudStudio 等纯静态托管）。
// 不设置该变量时保持默认的 server 模式（用于 docker-compose 的 next start）。
const isStaticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // 生产构建（next start）开启 gzip 压缩，减小传输体积
  compress: true,
  typescript: {
    // TypeScript 类型检查已全部通过，不再需要跳过
  },
  ...(isStaticExport
    ? {
        output: "export" as const,
        images: { unoptimized: true },
        trailingSlash: true,
      }
    : {}),
};

export default nextConfig;
