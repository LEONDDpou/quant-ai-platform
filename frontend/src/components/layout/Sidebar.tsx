"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Brain,
  LineChart,
  Newspaper,
  FlaskConical,
  Bot,
  CandlestickChart,
  TrendingUp,
  Zap,
  Boxes,
  Radar,
  Activity,
  PieChart,
  Bell,
  ChevronDown,
  Building2,
  Wallet,
  Trophy,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface NavGroup {
  label: string;
  items: {
    href: string;
    label: string;
    icon: React.ElementType;
    badge?: string;
  }[];
}

const navGroups: NavGroup[] = [
  {
    label: "交易终端",
    items: [
      { href: "/dashboard", label: "驾驶舱", icon: LayoutDashboard },
      { href: "/strategies", label: "策略中心", icon: Brain },
      { href: "/strategy-market", label: "策略市场", icon: Trophy },
      { href: "/ai-researcher", label: "AI研究员", icon: Bot },
    ],
  },
  {
    label: "分析工具",
    items: [
      { href: "/stock-analysis", label: "股票分析", icon: CandlestickChart },
      { href: "/news", label: "新闻情绪", icon: Newspaper },
      { href: "/factor-research", label: "因子研究", icon: Boxes },
      { href: "/stock-picker", label: "智能选股", icon: Radar },
      { href: "/institution", label: "机构动向", icon: Building2 },
    ],
  },
  {
    label: "市场监控",
    items: [
      { href: "/market-dynamics", label: "市场动态", icon: Activity },
    ],
  },
  {
    label: "交易管理",
    items: [
      { href: "/paper-trading", label: "模拟盘", icon: Wallet, badge: "NEW" },
      { href: "/portfolio", label: "组合管理", icon: PieChart },
      { href: "/trading", label: "自动交易", icon: LineChart },
      { href: "/alerts", label: "预警中心", icon: Bell },
    ],
  },
  {
    label: "研究工具",
    items: [
      { href: "/backtest", label: "回测系统", icon: FlaskConical },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  return (
    <aside className="w-[200px] flex-shrink-0 bg-[#0a0e1a] border-r border-[#151d2e] flex flex-col hidden lg:flex">
      {/* Logo */}
      <div className="h-14 flex items-center gap-2 px-4 border-b border-[#151d2e]">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
          <TrendingUp className="w-4 h-4 text-white" />
        </div>
        <div>
          <div className="text-xs font-bold text-slate-200">量化智投</div>
          <div className="text-[9px] text-slate-600">AI Quant Platform</div>
        </div>
      </div>

      {/* Nav Groups */}
      <nav className="flex-1 py-2 px-2 space-y-3 overflow-y-auto">
        {navGroups.map((group) => {
          const isCollapsed = collapsedGroups[group.label] || false;
          const hasActiveItem = group.items.some(
            (item) => pathname === item.href || pathname?.startsWith(item.href + "/")
          );

          return (
            <div key={group.label}>
              {/* Group Header */}
              <button
                onClick={() => toggleGroup(group.label)}
                className={cn(
                  "flex items-center gap-1 w-full px-2 py-1 text-left group",
                  hasActiveItem && "text-cyan-400"
                )}
              >
                <span
                  className={cn(
                    "text-[9px] font-semibold uppercase tracking-wider flex-1",
                    hasActiveItem ? "text-cyan-400" : "text-slate-600",
                    "group-hover:text-slate-400 transition-colors"
                  )}
                >
                  {group.label}
                </span>
                <ChevronDown
                  className={cn(
                    "w-3 h-3 text-slate-700 group-hover:text-slate-500 transition-transform duration-150",
                    isCollapsed && "-rotate-90"
                  )}
                />
              </button>

              {/* Group Items */}
              {!isCollapsed && (
                <div className="space-y-0.5 mt-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={cn("nav-link", isActive && "nav-link-active")}
                      >
                        <Icon className="w-4 h-4 flex-shrink-0" />
                        <span className="text-xs">{item.label}</span>
                        {isActive && (
                          <Zap className="w-3 h-3 ml-auto text-cyan-400 flex-shrink-0" />
                        )}
                        {item.badge && (
                          <span className="badge badge-orange ml-auto text-[9px]">{item.badge}</span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="p-3 border-t border-[#151d2e] space-y-1">
        <div className="px-3 py-2 text-[9px] text-slate-600 font-mono">
          AI 量化智能交易平台
        </div>
      </div>
    </aside>
  );
}
