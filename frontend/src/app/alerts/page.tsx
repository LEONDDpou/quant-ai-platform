"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Bell, Filter, AlertTriangle, Zap, Newspaper, Shield,
  BarChart3, TrendingUp, RefreshCw, Check,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getAlerts, markAlertRead, markAllAlertsRead, type AlertEntry, type AlertsResponse } from "@/lib/api";

const TYPE_ICONS: Record<string, React.ReactNode> = {
  technical: <BarChart3 size={13} />,
  capital: <TrendingUp size={13} />,
  event: <Newspaper size={13} />,
  risk: <Shield size={13} />,
};

const TYPE_LABELS: Record<string, string> = {
  technical: "技术信号",
  capital: "资金异动",
  event: "事件驱动",
  risk: "风控预警",
};

const SEVERITY_STYLES: Record<string, string> = {
  info: "bg-blue-950/50 text-blue-400 border-blue-700/30",
  warning: "bg-amber-950/50 text-amber-400 border-amber-700/30",
  critical: "bg-red-950/50 text-red-400 border-red-700/30",
};

const SEVERITY_ICONS: Record<string, React.ReactNode> = {
  info: <Bell size={13} />,
  warning: <AlertTriangle size={13} />,
  critical: <Zap size={13} />,
};

export default function AlertsPage() {
  const [alertData, setAlertData] = useState<AlertsResponse | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<string>("");

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAlerts(100, filter || undefined);
      setAlertData(data);
      setLastRefresh(new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    } catch (e) {
      console.error("Alert fetch error:", e);
    }
    setLoading(false);
  }, [filter]);

  useEffect(() => {
    fetchAlerts();
    const t = setInterval(fetchAlerts, 30000);
    return () => clearInterval(t);
  }, [fetchAlerts]);

  const handleMarkRead = async (id: number) => {
    try {
      await markAlertRead(id);
      await fetchAlerts();
    } catch (e) {}
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllAlertsRead();
      await fetchAlerts();
    } catch (e) {}
  };

  const alerts = alertData?.alerts || [];
  const filterTypes = ["", "technical", "capital", "event", "risk"];

  return (
    <div className="h-full overflow-auto bg-[#0b0f19]">
      <div className="max-w-5xl mx-auto p-4 space-y-4">
        {/* 顶栏 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-bold text-white">预警中心</h1>
            <p className="text-[11px] text-slate-500">Alert Center — 技术信号 · 资金异动 · 事件驱动 · 风控预警</p>
          </div>
          <div className="flex items-center gap-3">
            {lastRefresh && (
              <span className="text-[10px] text-slate-500">上次刷新 {lastRefresh}</span>
            )}
            <button
              onClick={fetchAlerts}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition-colors"
            >
              <RefreshCw size={12} className={cn(loading && "animate-spin")} />
              刷新
            </button>
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "全部", value: alertData?.total || 0, color: "text-white" },
            { label: "严重", value: alerts.filter(a => a.severity === "critical").length, color: "text-red-400" },
            { label: "警告", value: alerts.filter(a => a.severity === "warning").length, color: "text-amber-400" },
            { label: "未读", value: alerts.filter(a => !a.isRead).length, color: "text-blue-400" },
          ].map(s => (
            <div key={s.label} className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3 text-center">
              <div className="text-[10px] text-slate-400">{s.label}</div>
              <div className={cn("text-xl font-mono font-bold mt-1", s.color)}>{s.value}</div>
            </div>
          ))}
        </div>

        {/* 类型筛选 */}
        <div className="flex gap-1.5 flex-wrap">
          {filterTypes.map(t => (
            <button
              key={t || "all"}
              onClick={() => setFilter(t)}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded text-[11px] border transition-colors",
                filter === t
                  ? "border-blue-500 bg-blue-950/30 text-blue-400"
                  : "border-slate-700 text-slate-500 hover:text-slate-300",
              )}
            >
              {t ? TYPE_ICONS[t] : <Filter size={12} />}
              {t ? TYPE_LABELS[t] : "全部"}
            </button>
          ))}
        </div>

        {/* 预警列表 */}
        <div className="space-y-1.5">
          {alerts.map(alert => (
            <div
              key={alert.id}
              className={cn(
                "rounded-lg border p-3 transition-colors",
                alert.isRead ? "border-slate-700/30 bg-slate-800/30" : "border-slate-700/50 bg-slate-800/60",
                alert.severity === "critical" && !alert.isRead && "border-red-700/50 bg-red-950/10",
              )}
            >
              <div className="flex items-start gap-3">
                {/* 严重性图标 */}
                <div className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                  SEVERITY_STYLES[alert.severity],
                )}>
                  {SEVERITY_ICONS[alert.severity]}
                </div>

                {/* 内容 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] font-medium border",
                      SEVERITY_STYLES[alert.severity],
                    )}>
                      {alert.severity === "critical" ? "严重" : alert.severity === "warning" ? "警告" : "信息"}
                    </span>
                    <span className="text-[10px] text-slate-500 border border-slate-700/50 rounded px-1.5 py-0.5">
                      {TYPE_LABELS[alert.type] || alert.type}
                    </span>
                    {alert.code && (
                      <span className="text-[10px] text-slate-500 font-mono">{alert.code}</span>
                    )}
                    <span className="text-[10px] text-slate-600 ml-auto">
                      {alert.createdAt?.slice(11, 19) || ""}
                    </span>
                  </div>
                  <div className={cn(
                    "text-[12px] font-medium mb-0.5",
                    alert.isRead ? "text-slate-400" : "text-white",
                  )}>
                    {alert.title}
                  </div>
                  <div className="text-[10px] text-slate-500 line-clamp-2">
                    {alert.message}
                  </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex items-center gap-1 shrink-0">
                  {!alert.isRead && (
                    <button
                      onClick={() => handleMarkRead(alert.id)}
                      className="p-1 rounded hover:bg-slate-700/50 text-slate-500 hover:text-blue-400 transition-colors"
                      title="标记已读"
                    >
                      <Check size={13} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}

          {alerts.length === 0 && (
            <div className="py-16 text-center">
              <Bell size={32} className="text-slate-700 mx-auto mb-3" />
              <div className="text-xs text-slate-500">暂无预警</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
