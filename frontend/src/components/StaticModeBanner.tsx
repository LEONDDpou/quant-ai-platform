"use client";

import { API_BASE } from "@/lib/config";

/**
 * 静态部署无后端时，在页面顶部显示一个不显眼的灰色横幅。
 * 让"数据加载失败"等错误不再显得突兀——用户能理解这是演示环境。
 */
export function StaticModeBanner() {
  if (API_BASE) return null; // 有后端 → 不渲染

  return (
    <div className="bg-slate-800/60 border-b border-slate-700/50 px-4 py-1.5 text-[11px] text-slate-400 flex items-center justify-center gap-2">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-slate-500" />
      <span>
        静态演示模式 · 数据为模拟演示，不构成任何投资建议
      </span>
    </div>
  );
}
