"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchMarketplaceListings,
  fetchMySubscriptions,
  fetchMyPublishedStrategies,
  fetchMarketplaceLeaderboard,
  publishStrategy,
  subscribeMarketplaceStrategy,
  unsubscribeMarketplaceStrategy,
  rateMarketplaceStrategy,
  searchMarketplace,
  type MarketplaceListing,
  type PublishedStrategy,
  type MarketplaceLeaderboardEntry,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  BookOpen,
  Globe,
  List,
  Plus,
  Search,
  Star,
  ThumbsUp,
  Trophy,
  User,
  X,
} from "lucide-react";

type Tab = "browse" | "my-published" | "subscriptions" | "leaderboard";

export default function StrategyMarketplacePanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("browse");
  const [listings, setListings] = useState<MarketplaceListing[]>([]);
  const [published, setPublished] = useState<PublishedStrategy[]>([]);
  const [subs, setSubs] = useState<unknown[]>([]);
  const [leaderboard, setLeaderboard] = useState<MarketplaceLeaderboardEntry[]>([]);
  const [searchTag, setSearchTag] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // 发布表单
  const [showPublish, setShowPublish] = useState(false);
  const [pubName, setPubName] = useState("");
  const [pubDesc, setPubDesc] = useState("");
  const [pubTags, setPubTags] = useState("");
  const [pubRules, setPubRules] = useState("");

  const load = useCallback(async () => {
    if (accountId == null) return;
    setLoading(true);
    setError("");
    try {
      const [l, p, s, lb] = await Promise.all([
        fetchMarketplaceListings(50, 0),
        fetchMyPublishedStrategies(accountId),
        fetchMySubscriptions(accountId),
        fetchMarketplaceLeaderboard(20),
      ]);
      setListings(l);
      setPublished(p);
      setSubs(s);
      setLeaderboard(lb);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSearch = async () => {
    if (!searchTag.trim()) return load();
    setLoading(true);
    try {
      const r = await searchMarketplace(searchTag.trim());
      setListings(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "搜索失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (id: number) => {
    if (accountId == null) return;
    try {
      await subscribeMarketplaceStrategy({
        accountId,
        publishedStrategyId: id,
      });
      load();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "订阅失败");
    }
  };

  const handleUnsubscribe = async (id: number) => {
    if (accountId == null) return;
    try {
      await unsubscribeMarketplaceStrategy(accountId, id);
      load();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "取消订阅失败");
    }
  };

  const handleRate = async (id: number, score: number) => {
    if (accountId == null) return;
    try {
      await rateMarketplaceStrategy({
        accountId,
        publishedStrategyId: id,
        score,
      });
      load();
    } catch {
      // silent
    }
  };

  const handlePublish = async () => {
    if (accountId == null || !pubName.trim()) return;
    setLoading(true);
    try {
      let entryRules: unknown[] = [];
      let exitRules: unknown[] = [];
      try {
        const parsed = JSON.parse(pubRules || "[]");
        if (Array.isArray(parsed)) {
          entryRules = parsed.filter((r: unknown) => {
            if (typeof r === "object" && r !== null && "side" in r) {
              return (r as Record<string, unknown>).side === "entry";
            }
            return false;
          });
          exitRules = parsed.filter((r: unknown) => {
            if (typeof r === "object" && r !== null && "side" in r) {
              return (r as Record<string, unknown>).side !== "entry";
            }
            return false;
          });
        }
      } catch {
        // 解析失败则用空规则
      }
      await publishStrategy({
        accountId,
        name: pubName.trim(),
        description: pubDesc.trim(),
        tags: pubTags.split(",").map((t) => t.trim()).filter(Boolean),
        entryRules,
        exitRules,
      });
      setShowPublish(false);
      setPubName("");
      setPubDesc("");
      setPubTags("");
      setPubRules("");
      load();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "发布失败");
    } finally {
      setLoading(false);
    }
  };

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "browse", label: "市场浏览", icon: <Globe className="w-4 h-4" /> },
    { key: "my-published", label: "我的发布", icon: <User className="w-4 h-4" /> },
    { key: "subscriptions", label: "我的订阅", icon: <BookOpen className="w-4 h-4" /> },
    { key: "leaderboard", label: "排行榜", icon: <Trophy className="w-4 h-4" /> },
  ];

  return (
    <div className="card p-5 space-y-5">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <h2 className="section-title flex items-center gap-2">
          <Globe className="w-5 h-5" /> 策略市场
        </h2>
        <button
          className={cn(
            "btn-primary text-sm flex items-center gap-1",
            !accountId && "opacity-50 cursor-not-allowed",
          )}
          disabled={!accountId}
          onClick={() => setShowPublish(!showPublish)}
        >
          <Plus className="w-4 h-4" /> {showPublish ? "取消" : "发布策略"}
        </button>
      </div>

      {/* 发布表单 */}
      {showPublish && (
        <div className="border border-purple-200 rounded-lg p-4 space-y-3 bg-purple-50/30">
          <h3 className="text-sm font-semibold text-purple-700">发布策略到市场</h3>
          <input
            className="input w-full"
            placeholder="策略名称 *"
            value={pubName}
            onChange={(e) => setPubName(e.target.value)}
          />
          <textarea
            className="input w-full"
            placeholder="策略描述"
            rows={2}
            value={pubDesc}
            onChange={(e) => setPubDesc(e.target.value)}
          />
          <input
            className="input w-full"
            placeholder="标签（逗号分隔）"
            value={pubTags}
            onChange={(e) => setPubTags(e.target.value)}
          />
          <textarea
            className="input w-full font-mono text-xs"
            placeholder="规则 JSON（可选，{side, kind, params} 数组）"
            rows={3}
            value={pubRules}
            onChange={(e) => setPubRules(e.target.value)}
          />
          <button className="btn-primary text-sm" onClick={handlePublish} disabled={loading}>
            {loading ? "发布中..." : "确认发布"}
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b pb-2 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 text-xs rounded-t-md transition-colors whitespace-nowrap",
              tab === t.key
                ? "bg-purple-100 text-purple-700 font-semibold border-b-2 border-purple-500"
                : "text-gray-500 hover:text-gray-700 hover:bg-gray-50",
            )}
            onClick={() => setTab(t.key)}
          >
            {t.icon} {t.label}
          </button>
        ))}
        {/* 搜索栏 */}
        <div className="flex items-center gap-1 ml-auto">
          <input
            className="input text-xs w-28"
            placeholder="搜标签"
            value={searchTag}
            onChange={(e) => setSearchTag(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button className="btn-ghost text-xs p-1" onClick={handleSearch}>
            <Search className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded">{error}</div>
      )}

      {/* 浏览 */}
      {tab === "browse" && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {listings.length === 0 && (
            <div className="text-gray-400 text-xs py-8 text-center">暂无上架策略</div>
          )}
          {listings.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between p-3 rounded-lg border hover:shadow-sm transition-shadow"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">{item.name}</span>
                  <span className={cn(
                    "badge text-[10px]",
                    item.sourceType === "backtest" ? "badge-blue" : "badge-gray",
                  )}>
                    {item.sourceType}
                  </span>
                </div>
                <div className="text-xs text-gray-500 truncate mt-0.5">
                  {item.description || "暂无描述"}
                </div>
                <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-400">
                  <span className="flex items-center gap-0.5">
                    <Star className="w-3 h-3 text-yellow-500" /> {item.avgRating.toFixed(1)}
                  </span>
                  <span>{item.ratingCount} 评价</span>
                  <span>{item.subscriberCount} 订阅</span>
                  {item.tags?.map((tag) => (
                    <span key={tag} className="badge badge-gray text-[10px]">{tag}</span>
                  ))}
                </div>
              </div>
              <button
                className="btn-primary text-xs px-3 py-1"
                onClick={() => handleSubscribe(item.id)}
              >
                + 订阅
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 我的发布 */}
      {tab === "my-published" && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {published.length === 0 && (
            <div className="text-gray-400 text-xs py-8 text-center">你尚未发布策略</div>
          )}
          {published.map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between p-3 rounded-lg border"
            >
              <div>
                <div className="font-semibold text-sm">{p.name}</div>
                <div className="text-xs text-gray-500">{p.sourceType} · v{p.version}</div>
              </div>
              <span
                className={cn("badge text-xs", p.isPublished ? "badge-green" : "badge-red")}
              >
                {p.isPublished ? "已上架" : "已下架"}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 订阅 */}
      {tab === "subscriptions" && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {subs.length === 0 && (
            <div className="text-gray-400 text-xs py-8 text-center">暂无订阅</div>
          )}
          {subs.map((s: unknown) => {
            const sub = s as Record<string, unknown>;
            const ps = sub.publishedStrategy as Record<string, unknown> | null;
            return (
              <div
                key={sub.subId as number}
                className="flex items-center justify-between p-3 rounded-lg border"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm">
                    {(ps?.name as string) || "策略 #" + String(sub.publishedStrategyId)}
                  </div>
                  <div className="text-xs text-gray-500">
                    订阅于 {String(sub.subscribedAt || "").slice(0, 10)}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <button
                      key={s}
                      className="text-yellow-400 hover:scale-110 transition-transform"
                      onClick={() =>
                        handleRate(sub.publishedStrategyId as number, s)
                      }
                    >
                      <Star className="w-3.5 h-3.5" fill="currentColor" />
                    </button>
                  ))}
                  <button
                    className="btn-ghost text-xs text-red-500 ml-2"
                    onClick={() =>
                      handleUnsubscribe(sub.publishedStrategyId as number)
                    }
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 排行榜 */}
      {tab === "leaderboard" && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {leaderboard.length === 0 && (
            <div className="text-gray-400 text-xs py-8 text-center">暂无排行</div>
          )}
          {leaderboard.map((entry, idx) => (
            <div
              key={entry.publishedStrategyId}
              className="flex items-center justify-between p-3 rounded-lg border hover:shadow-sm transition-shadow"
            >
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
                    idx === 0
                      ? "bg-yellow-100 text-yellow-700"
                      : idx < 3
                        ? "bg-gray-100 text-gray-700"
                        : "text-gray-400",
                  )}
                >
                  {idx + 1}
                </span>
                <div>
                  <div className="font-semibold text-sm">{entry.name}</div>
                  <div className="flex items-center gap-3 text-[10px] text-gray-400">
                    <span>
                      <Star className="w-3 h-3 inline text-yellow-500" />{" "}
                      {entry.avgRating.toFixed(1)}
                    </span>
                    <span>{entry.ratingCount} 评价</span>
                    <span>{entry.subscriberCount} 订阅</span>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-purple-600">
                  {entry.compositeScore.toFixed(2)}
                </div>
                <div className="text-[10px] text-gray-400">综合分</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* loading */}
      {loading && (
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-2 border-purple-400 border-t-transparent" />
        </div>
      )}
    </div>
  );
}
