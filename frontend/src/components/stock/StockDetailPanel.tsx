"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  X,
  Building2,
  FileText,
  Newspaper,
  Radio,
  ExternalLink,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Globe,
  Phone,
  Mail,
  Calendar,
  User,
  MapPin,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getStockDetail,
  type StockDetail,
  type StockProfile,
  type StockFinance,
  type StockNewsItem,
} from "@/lib/api";

// ============================================================
// 工具
// ============================================================
function fmtAmt(raw: string | undefined): string {
  if (!raw) return "-";
  const v = parseFloat(raw);
  if (isNaN(v)) return raw;
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)} 亿`;
  if (abs >= 1e4) return `${(v / 1e4).toFixed(0)} 万`;
  return v.toFixed(0);
}

const FINANCE_KEYS: {
  label: string;
  key: string;
  unit?: "amt";
}[] = [
  { label: "营业收入", key: "OperatingRevenue", unit: "amt" },
  { label: "营业成本", key: "OperatingCost", unit: "amt" },
  { label: "营业利润", key: "OperatingProfit", unit: "amt" },
  { label: "利润总额", key: "TotalProfit", unit: "amt" },
  { label: "归母净利润", key: "NPParentCompanyOwners", unit: "amt" },
  { label: "基本每股收益", key: "BasicEPS" },
  { label: "研发费用", key: "RAndD", unit: "amt" },
];

const BS_KEYS: {
  label: string;
  key: string;
  unit?: "amt";
}[] = [
  { label: "总资产", key: "TotalAssets", unit: "amt" },
  { label: "总负债", key: "TotalLiability", unit: "amt" },
  { label: "归母权益", key: "TotalShareholderEquity", unit: "amt" },
  { label: "流动资产", key: "TotalCurrentAssets", unit: "amt" },
  { label: "流动负债", key: "TotalCurrentLiability", unit: "amt" },
  { label: "货币资金", key: "CashEquivalents", unit: "amt" },
  { label: "存货", key: "Inventories", unit: "amt" },
  { label: "商誉", key: "GoodWill", unit: "amt" },
  { label: "短期借款", key: "ShortTermLoan", unit: "amt" },
  { label: "长期借款", key: "LongtermLoan", unit: "amt" },
];

const CF_KEYS: {
  label: string;
  key: string;
  unit?: "amt";
}[] = [
  { label: "经营现金流", key: "NetOperateCashFlow", unit: "amt" },
  { label: "投资现金流", key: "NetInvestCashFlow", unit: "amt" },
  { label: "筹资现金流", key: "NetFinanceCashFlow", unit: "amt" },
  { label: "企业自由现金流", key: "FCFF", unit: "amt" },
  { label: "股权自由现金流", key: "FCFE", unit: "amt" },
  { label: "销售商品收到现金", key: "GoodsSaleServiceRenderCash", unit: "amt" },
];

// ============================================================
// 子组件
// ============================================================
function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
    </div>
  );
}

function ProfileTab({ profile }: { profile: StockProfile }) {
  const fields: { icon: React.ReactNode; label: string; value: string }[] = [
    {
      icon: <Building2 className="w-3.5 h-3.5" />,
      label: "行业分类",
      value: `${profile.industry || "-"} / ${profile.sector || "-"}`,
    },
    {
      icon: <FileText className="w-3.5 h-3.5" />,
      label: "主营业务",
      value: profile.business || "-",
    },
    {
      icon: <Calendar className="w-3.5 h-3.5" />,
      label: "上市日期",
      value: profile.listedDate || "-",
    },
    {
      icon: <Calendar className="w-3.5 h-3.5" />,
      label: "成立日期",
      value: profile.establishDate
        ? profile.establishDate.replace(" 00:00:00 +0800 CST", "")
        : "-",
    },
    {
      icon: <DollarSignMini />,
      label: "发行价 / 注册资本",
      value: `${profile.issuePrice || "-"} 元 / ${profile.regCapital || "-"} 万股`,
    },
    {
      icon: <User className="w-3.5 h-3.5" />,
      label: "董事长",
      value: profile.chairman || "-",
    },
    {
      icon: <Globe className="w-3.5 h-3.5" />,
      label: "公司网址",
      value: profile.website || "-",
    },
    {
      icon: <MapPin className="w-3.5 h-3.5" />,
      label: "注册地址",
      value: profile.regAddress || "-",
    },
    {
      icon: <MapPin className="w-3.5 h-3.5" />,
      label: "办公地址",
      value: profile.officeAddress || "-",
    },
    {
      icon: <Phone className="w-3.5 h-3.5" />,
      label: "联系电话",
      value: profile.tel || "-",
    },
    {
      icon: <Mail className="w-3.5 h-3.5" />,
      label: "电子邮箱",
      value: profile.email || "-",
    },
  ];

  return (
    <div className="space-y-1">
      {fields.map((f, i) => (
        <div
          key={i}
          className="flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-[#0d1220] transition-colors"
        >
          <span className="text-slate-500 mt-0.5 flex-shrink-0">{f.icon}</span>
          <div className="min-w-0">
            <span className="text-[10px] text-slate-500 block">{f.label}</span>
            <span className="text-xs text-slate-200 leading-relaxed break-words">
              {f.value}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function DollarSignMini() {
  return (
    <svg
      className="w-3.5 h-3.5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  );
}

function FinanceTable({
  data,
  keys,
}: {
  data: StockFinance[keyof StockFinance];
  keys: { label: string; key: string; unit?: string }[];
}) {
  if (!data || data.length === 0) {
    return <p className="text-xs text-slate-500 p-3">暂无财务数据</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#151d2e]">
            <th className="text-left px-3 py-2 text-slate-400 font-medium sticky left-0 bg-[#0a0e1a] z-10">
              指标
            </th>
            {data.map((row) => (
              <th
                key={row._date}
                className="text-right px-3 py-2 text-slate-400 font-medium whitespace-nowrap"
              >
                {row._date}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => (
            <tr
              key={k.key}
              className="border-b border-[#151d2e]/50 hover:bg-[#0d1220] transition-colors"
            >
              <td className="px-3 py-2 text-slate-400 sticky left-0 bg-[#0a0e1a]">
                {k.label}
              </td>
              {data.map((row) => {
                const v = row[k.key];
                const display =
                  k.unit === "amt" ? fmtAmt(v) : v || "-";
                return (
                  <td
                    key={row._date}
                    className="px-3 py-2 text-slate-200 text-right font-mono whitespace-nowrap"
                  >
                    {display}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FinanceTab({
  finance,
  subTab,
  setSubTab,
}: {
  finance: StockFinance;
  subTab: "lrb" | "zcfz" | "xjll";
  setSubTab: (v: "lrb" | "zcfz" | "xjll") => void;
}) {
  const tabs: { key: "lrb" | "zcfz" | "xjll"; label: string }[] = [
    { key: "lrb", label: "利润表" },
    { key: "zcfz", label: "资产负债表" },
    { key: "xjll", label: "现金流量表" },
  ];

  return (
    <div>
      <div className="flex gap-1 px-1 mb-3">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setSubTab(t.key)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              subTab === t.key
                ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/25"
                : "text-slate-500 hover:text-slate-300 border border-transparent",
            )}
          >
            {t.label}
          </button>
        ))}
        <span className="text-[10px] text-slate-600 ml-auto self-center">
          {finance[subTab]?.length || 0} 期
        </span>
      </div>
      <FinanceTable
        data={finance[subTab] || []}
        keys={
          subTab === "lrb"
            ? FINANCE_KEYS
            : subTab === "zcfz"
              ? BS_KEYS
              : CF_KEYS
        }
      />
    </div>
  );
}

function NewsList({ items, emptyText }: { items: StockNewsItem[]; emptyText: string }) {
  if (!items || items.length === 0) {
    return <p className="text-xs text-slate-500 p-3">{emptyText}</p>;
  }

  return (
    <div className="divide-y divide-[#151d2e] max-h-[500px] overflow-y-auto">
      {items.map((n, i) => (
        <div
          key={n.id || i}
          className="px-3 py-2.5 hover:bg-[#0d1220] transition-colors"
        >
          <div className="flex items-start gap-2">
            <div className="flex-1 min-w-0">
              <a
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-slate-200 hover:text-cyan-400 transition-colors line-clamp-2 leading-relaxed"
              >
                {n.title}
              </a>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] text-slate-600">{n.time?.slice(0, 16)}</span>
                {n.src && (
                  <span className="text-[10px] text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded">
                    {n.src}
                  </span>
                )}
              </div>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-600 flex-shrink-0 mt-0.5" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// 主面板
// ============================================================
interface StockDetailPanelProps {
  code: string;
  name?: string;
  onClose: () => void;
}

type TabKey = "profile" | "finance" | "news" | "live";

export default function StockDetailPanel({
  code,
  name: propName,
  onClose,
}: StockDetailPanelProps) {
  const [detail, setDetail] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<TabKey>("profile");
  const [subTab, setSubTab] = useState<"lrb" | "zcfz" | "xjll">("lrb");
  const panelRef = useRef<HTMLDivElement>(null);

  const fetchDetail = useCallback(async (force = false) => {
    setLoading(true);
    setError("");
    try {
      const data = await getStockDetail(code, force);
      setDetail(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // ESC 关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: "profile", label: "公司概况", icon: <Building2 className="w-3.5 h-3.5" /> },
    { key: "finance", label: "财务报表", icon: <FileText className="w-3.5 h-3.5" /> },
    { key: "news", label: "相关新闻", icon: <Newspaper className="w-3.5 h-3.5" /> },
    { key: "live", label: "实时动态", icon: <Radio className="w-3.5 h-3.5" /> },
  ];

  const displayName = detail?.name || propName || code;

  return (
    <>
      {/* 遮罩 */}
      <div
        className="fixed inset-0 bg-black/60 z-40"
        onClick={onClose}
      />

      {/* 面板 — 从右侧滑入 */}
      <div
        ref={panelRef}
        className={cn(
          "fixed top-0 right-0 h-full w-[520px] max-w-[95vw] z-50",
          "bg-[#060b15] border-l border-[#151d2e]",
          "flex flex-col shadow-2xl",
          "animate-slide-in",
        )}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#151d2e] flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-slate-100 truncate">
              {displayName}
            </h2>
            <p className="text-[10px] text-slate-600 font-mono">{code}</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => fetchDetail(true)}
              className="p-2 rounded-lg text-slate-500 hover:text-cyan-400 hover:bg-[#0d1220] transition-colors"
              title="强制刷新"
            >
              <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-[#0d1220] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* 标签页导航 */}
        <div className="flex border-b border-[#151d2e] px-3 flex-shrink-0">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors",
                tab === t.key
                  ? "border-cyan-400 text-cyan-400"
                  : "border-transparent text-slate-500 hover:text-slate-300",
              )}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto">
          {loading && <Spinner />}

          {error && !loading && (
            <div className="p-8 text-center">
              <p className="text-red-400 text-sm mb-2">加载失败: {error}</p>
              <button
                onClick={() => fetchDetail()}
                className="text-xs text-cyan-400 hover:underline"
              >
                重试
              </button>
            </div>
          )}

          {detail && !loading && (
            <div className="py-2">
              {/* Tab 1: 公司概况 */}
              {tab === "profile" && <ProfileTab profile={detail.profile} />}

              {/* Tab 2: 财务报表 */}
              {tab === "finance" && (
                <FinanceTab
                  finance={detail.finance}
                  subTab={subTab}
                  setSubTab={setSubTab}
                />
              )}

              {/* Tab 3: 相关新闻 */}
              {tab === "news" && (
                <NewsList
                  items={detail.news}
                  emptyText="暂无相关新闻"
                />
              )}

              {/* Tab 4: 实时动态 */}
              {tab === "live" && (
                <div>
                  <div className="flex items-center justify-between px-3 mb-2">
                    <span className="text-xs text-slate-400">
                      实时市场新闻（含提及 {displayName} 的动态）
                    </span>
                    <button
                      onClick={() => fetchDetail(true)}
                      className="flex items-center gap-1 text-[10px] text-cyan-500 hover:text-cyan-400 transition-colors"
                    >
                      <RefreshCw className="w-3 h-3" />
                      刷新
                    </button>
                  </div>
                  <NewsList
                    items={detail.marketNews}
                    emptyText="暂无实时动态"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* 底部时间戳 */}
        {detail && (
          <div className="px-5 py-2 border-t border-[#151d2e] flex-shrink-0">
            <p className="text-[10px] text-slate-600">
              数据更新: {detail.timestamp} · 点击刷新获取最新数据
            </p>
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        .animate-slide-in {
          animation: slideIn 0.25s ease-out;
        }
      `}</style>
    </>
  );
}
