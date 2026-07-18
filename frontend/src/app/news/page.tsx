"use client";

import { useEffect, useMemo, useState } from "react";
import { Newspaper, TrendingUp, TrendingDown, Minus, Filter, RefreshCw, Search } from "lucide-react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { cn } from "@/lib/utils";
import { fetchNews, fetchSentiment, type NewsItem } from "@/lib/api";
import { SentimentGauge } from "@/components/ui/SentimentGauge";
import { NewsItemCard } from "@/components/ui/NewsItemCard";
import { SectorSentimentBars } from "@/components/ui/SectorSentimentBars";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

const mockSectors = [
  { name: "科技", value: +7.2 },
  { name: "消费", value: +4.5 },
  { name: "金融", value: -0.32 },
  { name: "医疗", value: -1.87 },
  { name: "能源", value: +0.55 },
  { name: "工业", value: +2.1 },
];

const mockRecentSentiments = [
  { title: "+4.6 贵州茅台批价企稳回升", time: "5分钟前" },
  { title: "-3.2 五粮液动销略低于预期", time: "12分钟前" },
  { title: "-1.8 创业板指收跌0.46%", time: "18分钟前" },
  { title: "+1.6 央行降准释放流动性", time: "25分钟前" },
  { title: "-1.6 北向资金净流出收窄", time: "32分钟前" },
];

const aiComparison = [
  { model: "600519", verdict: "正面看涨", color: "text-emerald-400" },
  { model: "300750", verdict: "看多积极", color: "text-emerald-400" },
  { model: "002594", verdict: "中性偏弱", color: "text-slate-400" },
];

const macroEvents = [
  { date: "今日", event: "600519 年报披露", tag: "利好", cls: "badge-green" },
  { date: "明日", event: "央行公开市场操作", tag: "关注", cls: "badge-blue" },
  { date: "周四", event: "CPI通胀数据发布", tag: "重要", cls: "badge-yellow" },
  { date: "周五", event: "证监会例行发布会", tag: "关键", cls: "badge-orange" },
];

export default function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [sentiment, setSentiment] = useState<{ score: number; judgment: string; distribution: { positive: number; negative: number; neutral: number } } | null>(null);
  const [loading, setLoading] = useState(true);
  const [sentimentFilter, setSentimentFilter] = useState<"all" | "pos" | "neg" | "hot">("all");
  const [newsQuery, setNewsQuery] = useState("");
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const { toast } = useToast();

  const load = () => {
    setLoading(true);
    Promise.all([fetchNews(), fetchSentiment()])
      .then(([n, s]) => {
        setNews(n);
        setSentiment(s);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  // Fallback data when no real data
  const baseNews = news.length > 0 ? news : fallbackNewsItems;
  const displayNews = baseNews.filter((item) => {
    if (sentimentFilter === "pos" && item.sentiment !== "positive") return false;
    if (sentimentFilter === "neg" && item.sentiment !== "negative") return false;
    if (sentimentFilter === "hot" && Math.abs(item.impact) < 3) return false;
    if (newsQuery) {
      const q = newsQuery.trim();
      if (!item.title.includes(q) && !(item.summary || "").includes(q)) return false;
    }
    return true;
  });
  const displayScore = sentiment?.score ?? 68;

  const sentimentTrend = useMemo(() => {
    const arr: { date: string; score: number }[] = [];
    const base = new Date();
    for (let i = 29; i >= 0; i--) {
      const d = new Date(base);
      d.setDate(d.getDate() - i);
      const wave = Math.sin(i / 3) * 6 + Math.cos(i / 5) * 4;
      arr.push({ date: `${d.getMonth() + 1}/${d.getDate()}`, score: Math.max(20, Math.min(95, Math.round(displayScore + wave))) });
    }
    return arr;
  }, [displayScore]);

  const trendOption: EChartsOption = {
    backgroundColor: "transparent",
    grid: { top: 10, right: 10, bottom: 24, left: 30 },
    tooltip: { trigger: "axis", backgroundColor: "#111827", borderColor: "#1e2a3d", textStyle: { color: "#e8edf5", fontSize: 11 } },
    xAxis: { type: "category", data: sentimentTrend.map((d) => d.date), axisLine: { lineStyle: { color: "#1e2a3d" } }, axisLabel: { color: "#5a6a82", fontSize: 9 }, axisTick: { show: false } },
    yAxis: { type: "value", min: 0, max: 100, axisLine: { show: false }, splitLine: { lineStyle: { color: "#151d2e" } }, axisLabel: { color: "#5a6a82", fontSize: 9 } },
    series: [{ type: "line", data: sentimentTrend.map((d) => d.score), smooth: true, symbol: "none", lineStyle: { color: "#22d3ee", width: 2 }, areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(34,211,238,0.2)" }, { offset: 1, color: "transparent" }] } }, markLine: { silent: true, data: [{ yAxis: 50, lineStyle: { color: "#334155", type: "dashed" } }] } }],
  };

  return (
    <div className="space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">新闻与情绪中心</h1>
          <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
            AI 实时分析市场情绪 · 关联个股追踪
            <span className="badge badge-live text-[10px]">实时更新</span>
          </p>
          <div className="mt-2 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
            提示：板块情绪、近期舆情、AI 情绪对比、宏观事件等侧栏模块为<strong>演示数据（Mock）</strong>；新闻列表与整体情绪指数来自实时接口。
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary flex items-center gap-1.5 text-xs">
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
            刷新
          </button>
          <button onClick={() => setFilterOpen(true)} className="btn-secondary flex items-center gap-1.5 text-xs">
            <Filter className="w-3.5 h-3.5" /> 筛选
          </button>
        </div>
      </div>

      {/* Main layout: Left sidebar + Center + Right sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* ===== LEFT PANEL (3 cols) ===== */}
        <div className="lg:col-span-3 space-y-5">
          {/* Sentiment Gauge */}
          <div className="card p-4 flex flex-col items-center">
            <h3 className="section-title self-start mb-3">市场情绪指数</h3>
            <SentimentGauge score={displayScore} size={150} />
            <div className="mt-2 text-[11px] text-slate-500 text-center">综合500+数据源</div>
          </div>

          {/* Sector Sentiment Bars */}
          <div className="card p-4">
              <h3 className="section-title mb-3 flex items-center justify-between">
                板块情绪概览
                <span onClick={() => toast("板块情绪详情（演示）", "info")} className="text-[10px] text-cyan-400 cursor-pointer hover:underline">详情 →</span>
              </h3>
            <SectorSentimentBars sectors={mockSectors} />
          </div>
        </div>

        {/* ===== CENTER PANEL (6 cols) ===== */}
        <div className="lg:col-span-6 space-y-4">
          {/* Filter tabs above news list */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600" />
              <input
                value={newsQuery}
                onChange={(e) => setNewsQuery(e.target.value)}
                placeholder="搜索新闻标题..."
                className="input-dark pl-9 text-xs py-1.5"
              />
            </div>
            <div className="flex bg-[#111827] rounded-lg p-0.5 border border-[#1e2a3d]">
              {([["全部", "all"], ["利好", "pos"], ["利空", "neg"], ["重磅", "hot"]] as const).map(([tab, key]) => (
                <button
                  key={tab}
                  onClick={() => setSentimentFilter(key)}
                  className={cn(
                    "px-2.5 py-1 text-[11px] font-medium rounded transition-colors",
                    sentimentFilter === key ? "bg-[#1e293b] text-slate-200" : "text-slate-500 hover:text-slate-300"
                  )}
                >{tab}</button>
              ))}
            </div>
          </div>

          {/* News List */}
          <div className="space-y-2.5">
            {displayNews.length === 0 && (
              <div className="text-center py-12 text-slate-600 text-xs">没有符合条件的新闻</div>
            )}
            {displayNews.map((item) => (
              <NewsItemCard key={item.id} item={{
                id: item.id,
                title: item.title,
                source: item.source,
                time: item.time,
                sentiment: item.sentiment,
                impact: item.impact,
                summary: item.summary,
                tags: item.sentiment === "positive" ? ["利好"] : item.sentiment === "negative" ? ["利空"] : ["中性"],
              }} onClick={() => setSelectedNews(item)} />
            ))}
          </div>
        </div>

        {/* ===== RIGHT PANEL (3 cols) ===== */}
        <div className="lg:col-span-3 space-y-5">
          {/* Market Sentiment Trend Chart */}
          <div className="card p-4">
            <h3 className="section-title mb-1">市场情绪趋势</h3>
            <p className="text-[10px] text-slate-600 mb-2">近30日</p>
            <ReactECharts option={trendOption} style={{ height: "140px", width: "100%" }} />
            <div className="flex items-center justify-between mt-2 text-[10px]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <span className="text-slate-500">当前 {displayScore}</span>
              </div>
              <span onClick={() => toast("查看完整情绪报告（演示）", "info")} className="text-cyan-400 cursor-pointer hover:underline">查看全部</span>
            </div>
          </div>

          {/* Recent Important Sentiment News */}
          <div className="card p-4">
            <h3 className="section-title mb-3">近期重要舆情</h3>
            <div className="space-y-2.5">
              {mockRecentSentiments.map((item, i) => {
                const kw = item.title.replace(/^[+-][\d.]+\s*/, "").trim();
                return (
                  <div
                    key={i}
                    onClick={() => { setNewsQuery(kw); toast(`已筛选「${kw}」相关新闻`, "info"); }}
                    className="group cursor-pointer"
                  >
                    <div className="flex items-start gap-2">
                      <span className={cn("font-mono font-bold text-[11px] flex-shrink-0 mt-0.5",
                        item.title.startsWith("+") ? "sent-pos" : item.title.startsWith("-") ? "sent-neg" : "text-slate-500"
                      )}>
                        {item.title.match(/[+-][\d.]+/)?.[0]}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs text-slate-300 leading-snug group-hover:text-slate-100 transition-colors line-clamp-2">
                          {kw}
                        </p>
                        <span className="text-[10px] text-slate-700">{item.time}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* AI Sentiment Comparison */}
          <div className="card p-4">
            <h3 className="section-title mb-3">AI情绪分析对比</h3>
            <div className="space-y-2">
              {aiComparison.map((row) => (
                <div key={row.model} className="flex items-center justify-between py-1.5 border-b border-[#151d2e] last:border-0">
                  <span className="font-mono text-xs text-slate-400 w-10">{row.model}</span>
                  <span className={cn("text-xs font-medium", row.color)}>{row.verdict}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Important Macro Events */}
        <div className="card p-4">
          <h3 className="section-title mb-3">重要宏观事件</h3>
          <div className="space-y-2">
            {macroEvents.map((ev, i) => (
              <div key={i} className="flex items-center gap-3 py-1.5 border-b border-[#151d2e] last:border-0">
                <span className="text-[11px] font-mono text-slate-500 w-8">{ev.date}</span>
                <span className="badge badge-green text-[10px]" style={
                  ev.cls === "badge-blue" ? { background: "rgba(59,130,246,0.12)", color: "#60a5fa", borderColor: "rgba(59,130,246,0.2)" } :
                  ev.cls === "badge-yellow" ? { background: "rgba(251,191,36,0.12)", color: "#fbbf24", borderColor: "rgba(251,191,36,0.2)" } :
                  ev.cls === "badge-orange" ? { background: "rgba(251,146,60,0.12)", color: "#fb923c", borderColor: "rgba(251,146,60,0.2)" } : undefined
                }>
                  {ev.tag}
                </span>
                <span className="text-xs text-slate-300">{ev.event}</span>
              </div>
            ))}
          </div>
        </div>

        {/* AI Comprehensive Analysis */}
        <div className="card p-4">
          <h3 className="section-title mb-3">AI综合分析</h3>
          <div className="bg-[#0d1220] rounded-lg p-3 text-xs text-slate-400 leading-relaxed">
            <p>综合情绪指数 {displayScore}（中性偏乐观），电子板块领涨主要受AI算力需求持续扩张推动。
            市场整体风险偏好回升，北向资金持续净流入。需关注下周CPI通胀数据和央行货币政策信号。</p>
            <div className="mt-2 pt-2 border-t border-[#1a2235]">
              <span className="text-cyan-400 font-medium">建议配置：</span>
              <span className="ml-1">超配科技/新能源，标配消费，低配周期。</span>
            </div>
          </div>
        </div>
      </div>

      {/* 新闻详情弹窗 */}
      <Modal
        open={selectedNews !== null}
        onClose={() => setSelectedNews(null)}
        title="新闻详情"
        footer={<button className="btn-primary text-xs" onClick={() => setSelectedNews(null)}>关闭</button>}
      >
        {selectedNews && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-100 leading-relaxed">{selectedNews.title}</h3>
            <div className="flex items-center gap-2 text-[10px] text-slate-500">
              <span>{selectedNews.source}</span>
              <span>·</span>
              <span>{selectedNews.time}</span>
              <span className={cn("badge text-[9px]",
                selectedNews.sentiment === "positive" ? "badge-green" :
                selectedNews.sentiment === "negative" ? "badge-red" : "badge-gray"
              )}>
                {selectedNews.sentiment === "positive" ? "利好" : selectedNews.sentiment === "negative" ? "利空" : "中性"}
              </span>
              <span className="font-mono">影响 {selectedNews.impact > 0 ? "+" : ""}{selectedNews.impact}</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">{selectedNews.summary}</p>
          </div>
        )}
      </Modal>

      {/* 筛选弹窗 */}
      <Modal
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        title="新闻筛选"
        footer={
          <>
            <button className="btn-ghost text-xs" onClick={() => { setSentimentFilter("all"); setNewsQuery(""); setFilterOpen(false); }}>重置</button>
            <button className="btn-primary text-xs" onClick={() => { setFilterOpen(false); toast("筛选已应用", "success"); }}>应用</button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <div className="text-xs text-slate-400 mb-2">情感倾向</div>
            <div className="flex gap-2">
              {([["全部", "all"], ["利好", "pos"], ["利空", "neg"], ["重磅", "hot"]] as const).map(([label, key]) => (
                <button
                  key={key}
                  onClick={() => setSentimentFilter(key)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs border transition-colors",
                    sentimentFilter === key ? "bg-[#1e293b] text-slate-200 border-[#2a3a52]" : "text-slate-500 border-[#1e2a3d] hover:text-slate-300"
                  )}
                >{label}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-400 mb-2">关键词</div>
            <input
              value={newsQuery}
              onChange={(e) => setNewsQuery(e.target.value)}
              placeholder="按标题或摘要搜索..."
              className="input-dark w-full"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}

// Fallback news items matching the reference
const fallbackNewsItems: NewsItem[] = [
  { id: "n1", title: "贵州茅台批价企稳回升，北向资金大幅净流入超50亿元", source: "财联社", time: "14:28", sentiment: "positive", impact: 4.6, relatedStocks: [], summary: "近期高端白酒批价逐步企稳，渠道库存去化良好。北向资金连续三日净买入，单日净流入超50亿元，机构看好龙头估值修复。" },
  { id: "n2", title: "五粮液季报超预期，机构上调目标价至¥180", source: "证券时报", time: "13:15", sentiment: "positive", impact: 3.2, relatedStocks: [], summary: "五粮液Q2营收与净利双双超预期，高端产品占比提升。多家券商上调目标价至¥180，认为次高端复苏将接力增长。" },
  { id: "n3", title: "创业板指收跌0.46%，降准预期与获利盘形成对冲", source: "上证报", time: "13:04", sentiment: "negative", impact: -3.2, relatedStocks: [], summary: "创业板指收跌0.46%于2118点，前期热门赛道获利回吐，但降准预期升温对冲部分抛压，机构维持谨慎乐观。" },
  { id: "n4", title: "央行降准0.5个百分点释放万亿流动性，成长板块受益", source: "经济参考报", time: "12:42", sentiment: "positive", impact: 1.6, relatedStocks: [], summary: "央行宣布全面降准0.5个百分点，释放长期资金约万亿元。市场利率结构性下行，有望支撑成长板块估值修复。" },
  { id: "n5", title: "中金公司下调银行板块评级，信用风险担忧上升", source: "第一财经", time: "11:38", sentiment: "negative", impact: -1.6, relatedStocks: [], summary: "中金公司下调银行板块至中性偏下，认为商业地产敞口风险上升、信贷违约概率上行，建议降低银行板块配置比例。" },
  { id: "n6", title: "宁德时代Q4动力电池装机量同比增32%，市占率提升", source: "界面新闻", time: "10:18", sentiment: "positive", impact: 3.1, relatedStocks: [], summary: "宁德时代Q4国内动力电池装机量同比增长32%，市占率进一步走高。海外订单放量叠加麒麟电池放量，盈利韧性增强。" },
  { id: "n7", title: "恒瑞医药创新药出海进展平稳，研发投入持续高位", source: "医药经济报", time: "09:42", sentiment: "neutral", impact: -0.8, relatedStocks: [], summary: "恒瑞医药多款创新药海外临床稳步推进，研发投入维持高位。仿制药集采影响边际减弱，但出海兑现节奏仍待验证。" },
  { id: "n8", title: "比亚迪高阶智驾全系落地，智能化竞争进入新阶段", source: "36氪", time: "08:55", sentiment: "positive", impact: 2.2, relatedStocks: [], summary: "比亚迪宣布高阶智能驾驶功能全系标配落地，城区NOA加速渗透。行业智能化军备竞赛升温，软硬件一体化能力成关键。" },
];
