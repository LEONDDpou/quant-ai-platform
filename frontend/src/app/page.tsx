"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// 客户端重定向到 dashboard（兼容静态导出：服务端 redirect() 在 export 模式下会报错）
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);
  return null;
}
