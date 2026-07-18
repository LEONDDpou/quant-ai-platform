"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Send, Clock, TrendingUp, Wallet, Shield,
  RefreshCw, Check, X, AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getPortfolioOverview, getPortfolioPositions, getPortfolioOrders,
  placePortfolioOrder, cancelPortfolioOrder,
  type PortfolioOverview, type PortfolioPosition, type PortfolioOrder,
} from "@/lib/api";

// ── 格式化 ──
function fmtMoney(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function fmtPct(v: number): string {
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

// ── 风控配置 ──
const RISK_CONFIG = {
  maxPosition: 25,
  dailyLossLimit: 5,
  maxDrawdownLimit: 15,
  stopLoss: 8,
  takeProfit: 20,
};

export default function TradingPage() {
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);
  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [orders, setOrders] = useState<PortfolioOrder[]>([]);
  const [loading, setLoading] = useState(true);

  // 下单表单
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [direction, setDirection] = useState<"buy" | "sell">("buy");
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");
  const [orderStatus, setOrderStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [placing, setPlacing] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, pos, ord] = await Promise.all([
        getPortfolioOverview(),
        getPortfolioPositions(),
        getPortfolioOrders(50),
      ]);
      setOverview(ov);
      setPositions(pos);
      setOrders(ord);
    } catch (e) {
      console.error("Trading fetch error:", e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // 从持仓快速选择
  const handleSelectPosition = (pos: PortfolioPosition) => {
    setCode(pos.code);
    setName(pos.name);
    setPrice(pos.currentPrice.toFixed(2));
  };

  // 下单
  const handlePlaceOrder = async () => {
    if (!code || !direction || !shares) return;
    setPlacing(true);
    setOrderStatus(null);
    try {
      const result = await placePortfolioOrder({
        code,
        name: name || code,
        direction,
        shares: parseInt(shares),
        price: price ? parseFloat(price) : undefined,
        reason,
      });
      if (result.status === "filled") {
        setOrderStatus({ type: "success", msg: result.message || "订单成交" });
        setCode(""); setName(""); setShares(""); setPrice(""); setReason("");
        await fetchData();
      } else {
        setOrderStatus({ type: "error", msg: result.error || "下单失败" });
      }
    } catch (e: any) {
      setOrderStatus({ type: "error", msg: e.message || "下单失败" });
    }
    setPlacing(false);
  };

  const handleCancel = async (orderId: number) => {
    try {
      await cancelPortfolioOrder(orderId);
      await fetchData();
    } catch (e) {}
  };

  return (
    <div className="h-full overflow-auto bg-[#0b0f19]">
      <div className="max-w-6xl mx-auto p-4 space-y-4">
        {/* 顶栏 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-bold text-white">自动交易</h1>
            <p className="text-[11px] text-slate-500">Trading Desk — 模拟账户 · 下单 · 风控</p>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            <RefreshCw size={12} className={cn(loading && "animate-spin")} />
            刷新
          </button>
        </div>

        {/* 资产概览 */}
        {overview && (
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "总资产", value: `¥${fmtMoney(overview.totalValue)}`, color: "text-white", icon: <Wallet size={14} /> },
              { label: "现金", value: `¥${fmtMoney(overview.cash)}`, color: "text-emerald-400", icon: <Wallet size={14} /> },
              { label: "持仓市值", value: `¥${fmtMoney(overview.positionValue)}`, color: "text-blue-400", icon: <TrendingUp size={14} /> },
              { label: "累计收益", value: fmtPct(overview.totalReturn), color: overview.totalReturn >= 0 ? "text-emerald-400" : "text-red-400", icon: <TrendingUp size={14} /> },
            ].map(c => (
              <div key={c.label} className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
                <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1">
                  {c.icon} {c.label}
                </div>
                <div className={cn("text-base font-mono font-bold tabular-nums", c.color)}>
                  {c.value}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* ── 左侧：下单表单 ── */}
          <div className="space-y-4">
            <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-4">
              <div className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <Send size={14} /> 模拟下单
              </div>
              {/* 方向 */}
              <div className="flex gap-2 mb-3">
                {(["buy", "sell"] as const).map(d => (
                  <button
                    key={d}
                    onClick={() => setDirection(d)}
                    className={cn(
                      "flex-1 py-2 rounded text-[12px] font-medium transition-colors",
                      direction === d
                        ? d === "buy"
                          ? "bg-emerald-600 text-white"
                          : "bg-red-600 text-white"
                        : "bg-slate-700/50 text-slate-400 hover:text-white",
                    )}
                  >
                    {d === "buy" ? "买入" : "卖出"}
                  </button>
                ))}
              </div>
              {/* 代码 */}
              <div className="mb-2">
                <label className="text-[10px] text-slate-400">股票代码</label>
                <input
                  value={code}
                  onChange={e => setCode(e.target.value)}
                  placeholder="e.g. sh600519"
                  className="w-full mt-1 px-2.5 py-1.5 rounded text-[12px] font-mono bg-slate-900 border border-slate-700 text-white focus:border-blue-500 outline-none"
                />
              </div>
              {/* 名称 */}
              <div className="mb-2">
                <label className="text-[10px] text-slate-400">名称（可选）</label>
                <input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="贵州茅台"
                  className="w-full mt-1 px-2.5 py-1.5 rounded text-[12px] bg-slate-900 border border-slate-700 text-white focus:border-blue-500 outline-none"
                />
              </div>
              {/* 数量 & 价格 */}
              <div className="grid grid-cols-2 gap-2 mb-2">
                <div>
                  <label className="text-[10px] text-slate-400">数量（股）</label>
                  <input
                    value={shares}
                    onChange={e => setShares(e.target.value)}
                    type="number"
                    min="100"
                    step="100"
                    placeholder="100"
                    className="w-full mt-1 px-2.5 py-1.5 rounded text-[12px] font-mono bg-slate-900 border border-slate-700 text-white focus:border-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">价格（留空=市价）</label>
                  <input
                    value={price}
                    onChange={e => setPrice(e.target.value)}
                    type="number"
                    step="0.01"
                    placeholder="市价"
                    className="w-full mt-1 px-2.5 py-1.5 rounded text-[12px] font-mono bg-slate-900 border border-slate-700 text-white focus:border-blue-500 outline-none"
                  />
                </div>
              </div>
              {/* 理由 */}
              <div className="mb-3">
                <label className="text-[10px] text-slate-400">交易理由（可选）</label>
                <input
                  value={reason}
                  onChange={e => setReason(e.target.value)}
                  placeholder="根据AI研判增配消费"
                  className="w-full mt-1 px-2.5 py-1.5 rounded text-[12px] bg-slate-900 border border-slate-700 text-white focus:border-blue-500 outline-none"
                />
              </div>
              {/* 预估 */}
              {shares && shares !== "0" && (
                <div className="rounded bg-slate-900/50 p-2 mb-3 text-[10px]">
                  <div className="text-slate-400">
                    预估{price ? "金额" : "市价金额"}:{" "}
                    <span className="font-mono text-white">
                      ¥{fmtMoney((parseFloat(price || "0") || 0) * parseInt(shares) || 0)}
                    </span>
                  </div>
                </div>
              )}
              {/* 下单按钮 */}
              <button
                onClick={handlePlaceOrder}
                disabled={placing || !code || !shares}
                className={cn(
                  "w-full py-2 rounded text-[12px] font-bold transition-colors",
                  direction === "buy"
                    ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                    : "bg-red-600 hover:bg-red-500 text-white",
                  (placing || !code || !shares) && "opacity-50 cursor-not-allowed",
                )}
              >
                {placing ? "提交中..." : `${direction === "buy" ? "买入" : "卖出"} ${name || code}`}
              </button>
              {/* 状态 */}
              {orderStatus && (
                <div className={cn(
                  "mt-2 p-2 rounded text-[11px] flex items-center gap-1.5",
                  orderStatus.type === "success"
                    ? "bg-emerald-950/30 border border-emerald-700/30 text-emerald-400"
                    : "bg-red-950/30 border border-red-700/30 text-red-400",
                )}>
                  {orderStatus.type === "success" ? <Check size={12} /> : <X size={12} />}
                  {orderStatus.msg}
                </div>
              )}
            </div>

            {/* 持仓快速选择 */}
            {positions.length > 0 && (
              <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 p-3">
                <div className="text-[11px] text-slate-400 mb-2">快速选择</div>
                <div className="space-y-1">
                  {positions.map(p => (
                    <button
                      key={p.code}
                      onClick={() => handleSelectPosition(p)}
                      className="w-full text-left px-2 py-1.5 rounded text-[11px] bg-slate-900/50 hover:bg-slate-700/50 transition-colors flex items-center justify-between"
                    >
                      <span className="text-slate-300">{p.name}</span>
                      <span className="text-slate-500 font-mono">¥{p.currentPrice.toFixed(2)}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── 右侧：订单历史 + 风控 ── */}
          <div className="lg:col-span-2 space-y-4">
            {/* 风控面板 */}
            <div className="rounded-lg border border-amber-700/30 bg-amber-950/10 p-3">
              <div className="flex items-center gap-2 mb-2">
                <Shield size={14} className="text-amber-400" />
                <span className="text-[12px] font-bold text-amber-400">风控配置</span>
              </div>
              <div className="grid grid-cols-5 gap-2 text-[10px]">
                {[
                  { label: "最大仓位", value: `${RISK_CONFIG.maxPosition}%` },
                  { label: "日亏损上限", value: `-${RISK_CONFIG.dailyLossLimit}%` },
                  { label: "最大回撤", value: `-${RISK_CONFIG.maxDrawdownLimit}%` },
                  { label: "止损线", value: `-${RISK_CONFIG.stopLoss}%` },
                  { label: "止盈线", value: `+${RISK_CONFIG.takeProfit}%` },
                ].map(r => (
                  <div key={r.label} className="text-center py-1.5 rounded bg-slate-800/60 border border-slate-700/30">
                    <div className="text-slate-500 mb-0.5">{r.label}</div>
                    <div className="font-mono font-bold text-amber-300">{r.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* 订单历史 */}
            <div className="rounded-lg border border-slate-700/50 bg-slate-800/60 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
                <div className="text-[12px] font-bold text-white flex items-center gap-2">
                  <Clock size={13} /> 订单历史
                </div>
                <span className="text-[10px] text-slate-500">最近 {orders.length} 笔</span>
              </div>
              <table className="w-full text-[11px]">
                <thead className="bg-slate-800/80 text-slate-400">
                  <tr>
                    <th className="py-2 px-3 text-left">时间</th>
                    <th className="py-2 px-2 text-left">代码</th>
                    <th className="py-2 px-2 text-left">名称</th>
                    <th className="py-2 px-2 text-center">方向</th>
                    <th className="py-2 px-2 text-right">价格</th>
                    <th className="py-2 px-2 text-right">数量</th>
                    <th className="py-2 px-2 text-right">金额</th>
                    <th className="py-2 px-2 text-center">状态</th>
                    <th className="py-2 px-2 text-center">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o, i) => (
                    <tr key={o.id} className={cn("border-t border-slate-700/30", i % 2 === 0 ? "bg-slate-800/20" : "")}>
                      <td className="py-2 px-3 text-slate-500 text-[10px]">
                        {o.createdAt?.slice(0, 19)?.replace("T", " ") || ""}
                      </td>
                      <td className="py-2 px-2 text-slate-500 font-mono text-[10px]">{o.code}</td>
                      <td className="py-2 px-2 text-white">{o.name}</td>
                      <td className="py-2 px-2 text-center">
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-medium",
                          o.direction === "buy"
                            ? "bg-emerald-950/50 text-emerald-400"
                            : "bg-red-950/50 text-red-400",
                        )}>
                          {o.direction === "buy" ? "买入" : "卖出"}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-right text-slate-300 font-mono">¥{o.price.toFixed(2)}</td>
                      <td className="py-2 px-2 text-right text-white font-mono">{o.shares}</td>
                      <td className="py-2 px-2 text-right text-white font-mono">¥{fmtMoney(o.amount)}</td>
                      <td className="py-2 px-2 text-center">
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px]",
                          o.status === "filled" ? "bg-emerald-950/30 text-emerald-400" :
                          o.status === "pending" ? "bg-amber-950/30 text-amber-400" :
                          "bg-slate-700/30 text-slate-500",
                        )}>
                          {o.status === "filled" ? "成交" : o.status === "pending" ? "待执行" : "已撤"}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-center">
                        {o.status === "pending" && (
                          <button
                            onClick={() => handleCancel(o.id)}
                            className="text-[10px] text-red-400 hover:text-red-300"
                          >
                            撤单
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {orders.length === 0 && (
                    <tr>
                      <td colSpan={9} className="py-6 text-center text-slate-500 text-xs">
                        暂无订单记录
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
