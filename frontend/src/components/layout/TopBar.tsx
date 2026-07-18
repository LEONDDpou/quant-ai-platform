"use client";

import { useState, useEffect } from "react";
import {
  Search, Bell, ChevronDown,
  TrendingUp, LayoutDashboard, Brain, CandlestickChart,
  Newspaper, FlaskConical, LineChart, Bot, Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";

const topNavItems = [
  { href: "/dashboard", label: "仪表盘", icon: LayoutDashboard },
  { href: "/trading", label: "自动交易", icon: LineChart },
  { href: "/strategies", label: "AI策略", icon: Brain },
  { href: "/stock-analysis", label: "策略行情", icon: CandlestickChart },
  { href: "/backtest", label: "策略回测", icon: FlaskConical },
  { href: "/news", label: "持仓管理", icon: Newspaper },
  { href: "/ai-researcher", label: "AI助手", icon: Bot },
];

export function TopBar() {
  const [time, setTime] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const [search, setSearch] = useState("");
  const pathname = usePathname();
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(
        now.toLocaleString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          timeZone: "Asia/Shanghai",
        })
      );
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  const notifications = [
    { id: 1, text: "600519.SH 触发高置信度买入信号（91%）", time: "14:31", level: "buy" as const },
    { id: 2, text: "风控预警：002594.SZ 仓位接近上限", time: "13:58", level: "warn" as const },
    { id: 3, text: "财报日历：600036.SH 季报将于明日披露", time: "13:20", level: "info" as const },
    { id: 4, text: "自动交易已执行 12 笔，今日盈亏 +¥23,840", time: "12:45", level: "buy" as const },
  ];

  const onSearchEnter = () => {
    const q = search.trim();
    if (!q) return;
    // 形如 600519 / 300750.SZ 视为股票代码 → 诊股；否则按策略名搜索
    if (/^\d{4,6}(\.(SH|SZ|BJ))?$/.test(q)) {
      router.push(`/stock-analysis?code=${q.replace(/\.(SH|SZ|BJ)$/i, "")}`);
    } else {
      router.push(`/strategies?search=${encodeURIComponent(q)}`);
    }
    setSearch("");
  };

  return (
    <header className="h-14 flex-shrink-0 bg-[#0a0e1a]/95 backdrop-blur-md border-b border-[#151d2e] flex items-center px-4 gap-3">
      {/* Logo */}
      <div className="flex items-center gap-2 mr-2">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
          <TrendingUp className="w-4 h-4 text-white" />
        </div>
        <span className="text-sm font-bold text-slate-200 hidden sm:inline">AI A股量化</span>
      </div>

      {/* Horizontal Nav */}
      <nav className="hidden lg:flex items-center gap-0.5 flex-1">
        {topNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href}
              className={cn("top-nav-item", isActive && "top-nav-item-active")}
            >
              <Icon className="w-3.5 h-3.5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Search (centered on large screens) */}
      <div className="flex-1 max-w-xs mx-auto hidden md:block">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearchEnter()}
            type="text"
            placeholder="搜索策略 / 股票代码..."
            className="w-full bg-[#0d1220] border border-[#1a2235] rounded-lg pl-8 pr-3 py-1.5 text-xs 
                     text-slate-300 placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
        </div>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-2 ml-auto">
        {/* 行情迷你条已移除：原先为硬编码假数据（600519.SH ¥1685.0 等），
            会误导用户以为已接入真实行情；后续如需展示实时报价，应接入真实接口。 */}

        {/* Quick trade button */}
        <button
          onClick={() => router.push("/trading")}
          className="btn-primary px-3 py-1 text-xs flex items-center gap-1"
        >
          + 快捷交易
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen((v) => !v)}
            className="relative btn-icon"
            aria-label="通知"
          >
            <Bell className="w-4 h-4 text-slate-400" />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-red-400 rounded-full" />
          </button>
          {notifOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-[#0f1626] border border-[#1e2a3d] rounded-xl shadow-2xl shadow-black/50 z-50 animate-slide-up overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1a2235]">
                <span className="text-xs font-semibold text-slate-200">通知中心</span>
                <button
                  onClick={() => toast("已标记全部通知为已读", "success")}
                  className="text-[10px] text-cyan-400 hover:underline"
                >全部已读</button>
              </div>
              <div className="max-h-72 overflow-y-auto">
                {notifications.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => { setNotifOpen(false); toast(n.text, n.level === "warn" ? "error" : "info"); }}
                    className="w-full text-left px-4 py-2.5 border-b border-[#151d2e] last:border-0 hover:bg-white/[0.03] transition-colors flex items-start gap-2"
                  >
                    <span className={cn(
                      "mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0",
                      n.level === "buy" ? "bg-emerald-400" : n.level === "warn" ? "bg-red-400" : "bg-cyan-400"
                    )} />
                    <span className="min-w-0">
                      <span className="block text-[11px] text-slate-300 leading-snug">{n.text}</span>
                      <span className="text-[10px] text-slate-600">{n.time}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* User avatar */}
        <div
          onClick={() => toast("账户中心（演示）", "info")}
          className="flex items-center gap-1.5 cursor-pointer hover:bg-white/5 px-2 py-1 rounded-lg transition-colors"
        >
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center text-[10px] font-bold text-white">
            Q
          </div>
          <ChevronDown className="w-3 h-3 text-slate-500" />
        </div>
      </div>
    </header>
  );
}
