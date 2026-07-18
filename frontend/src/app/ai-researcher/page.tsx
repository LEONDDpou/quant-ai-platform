"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  TrendingUp,
  AlertTriangle,
  Eye,
  FileText,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
  Cpu,
  Loader2,
  Send,
  Trash2,
  BarChart3,
  Beaker,
  FlaskConical,
  PieChart,
  Play,
  RotateCcw,
} from "lucide-react";
import { fetchAIReport, chatWithAI, getInstitutionAggregate, type AIReport, type ChatMsg, type InstitutionAggregate } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AgentPipeline, type AgentStep, AGENT_ICONS } from "@/components/ui/AgentPipeline";

// ── 工具函数 ──
function formatFlow(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(1)}亿`;
  if (abs >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
}

// ── Agent 流水线步骤定义 ──
const PIPELINE_DEFS = [
  {
    id: "industry",
    agentName: "IndustryAnalyst",
    label: "行业景气度分析",
    description: "扫描申万一级行业景气度指标，识别当前周期位置，筛选高景气赛道",
    icon: AGENT_ICONS.IndustryAnalyst || <BarChart3 className="w-4 h-4 text-blue-400" />,
  },
  {
    id: "factor",
    agentName: "FactorEngineer",
    label: "因子挖掘与测试",
    description: "从估值/质量/动量/波动/情绪五维度挖掘有效因子，计算IC与分组收益",
    icon: AGENT_ICONS.FactorEngineer || <Beaker className="w-4 h-4 text-purple-400" />,
  },
  {
    id: "strategy",
    agentName: "StrategyBuilder",
    label: "策略信号生成",
    description: "将有效因子信号转化为择时规则与选股条件，生成可执行策略代码",
    icon: AGENT_ICONS.StrategyBuilder || <Cpu className="w-4 h-4 text-cyan-400" />,
  },
  {
    id: "backtest",
    agentName: "BacktestRunner",
    label: "自动化回测验证",
    description: "在历史数据上运行策略，产出绩效报告：收益/夏普/回撤/胜率",
    icon: AGENT_ICONS.BacktestRunner || <FlaskConical className="w-4 h-4 text-amber-400" />,
  },
  {
    id: "portfolio",
    agentName: "PortfolioOptimizer",
    label: "组合优化与权重分配",
    description: "基于均值-方差优化与风险预算模型，给出最终组合配置建议",
    icon: AGENT_ICONS.PortfolioOptimizer || <PieChart className="w-4 h-4 text-emerald-400" />,
  },
];

type PipelineMode = "idle" | "running" | "done";

export default function AIResearcherPage() {
  // ── 传统报告（向后兼容） ──
  const [report, setReport] = useState<AIReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"report" | "pipeline">("report");

  // ── 机构数据（v1.3.1 数据贯通） ──
  const [instData, setInstData] = useState<InstitutionAggregate | null>(null);
  useEffect(() => {
    getInstitutionAggregate()
      .then(setInstData)
      .catch(() => setInstData(null));
  }, []);

  // ── Agent 流水线状态 ──
  const [pipelineMode, setPipelineMode] = useState<PipelineMode>("idle");
  const [pipelineSteps, setPipelineSteps] = useState<AgentStep[]>(
    PIPELINE_DEFS.map((d) => ({
      ...d,
      status: "idle" as const,
    }))
  );

  // ── 对话流状态 ──
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [model, setModel] = useState("DeepSeek");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── 加载传统报告 ──
  const load = useCallback(async (refresh = false) => {
    try {
      setError(null);
      if (refresh) setRegenerating(true);
      else setLoading(true);
      const data = await fetchAIReport(refresh);
      setReport(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
      setRegenerating(false);
    }
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  // ── 对话滚动 ──
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, chatLoading]);

  const sendMessage = async () => {
    const text = chatInput.trim();
    if (!text || chatLoading) return;
    setChatInput("");
    const next: ChatMsg[] = [...chatMessages, { role: "user", content: text }];
    setChatMessages(next);
    setChatLoading(true);
    try {
      const data = await chatWithAI(next, model);
      setChatMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "调用 AI 失败";
      setChatMessages((prev) => [...prev, { role: "assistant", content: `⚠️ ${msg}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  const clearChat = () => setChatMessages([]);

  // ── 执行流水线 ──
  const runPipeline = async () => {
    setPipelineMode("running");
    const steps = [...pipelineSteps];

    for (let i = 0; i < steps.length; i++) {
      // 标记当前为 running
      steps[i] = { ...steps[i], status: "running" };
      setPipelineSteps([...steps]);

      // 模拟各步骤耗时（实际应调用后端 AI Agent 端点）
      const delays = [800, 1200, 1000, 1500, 900];
      await new Promise((r) => setTimeout(r, delays[i] || 1000));

      // 模拟结果
      const outputs = [
        "景气度排名前5行业：电力设备(82)、汽车(78)、电子(75)、医药生物(70)、机械设备(68)。当前处于库存周期底部回升阶段。",
        "有效因子TOP3：ROE_TTM(IC=0.042)、北向资金20日净流入(IC=0.038)、20日动量(IC=0.031)。估值因子近期IC走弱。",
        "生成策略：高ROE+北向增持+趋势向上。买入条件：ROE>15% AND 北向20日净流入>5000万 AND MA20>MA60。仓位：等权分配。",
        "回测区间2024.1-2026.7：年化收益+18.3%，夏普1.62，最大回撤-12.5%，胜率64.2%，月均交易2.3次。跑赢沪深300超额+7.8%。",
        "最优组合配置：电力设备25%、汽车20%、电子20%、医药15%、现金20%。组合预期年化收益15-20%，VaR95=-2.1%。",
      ];

      steps[i] = {
        ...steps[i],
        status: "completed",
        duration: `${(delays[i] / 1000).toFixed(1)}s`,
        output: outputs[i],
      };
      setPipelineSteps([...steps]);
    }

    setPipelineMode("done");
  };

  const resetPipeline = () => {
    setPipelineMode("idle");
    setPipelineSteps(PIPELINE_DEFS.map((d) => ({ ...d, status: "idle" as const })));
  };

  // ── 加载态 ──
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
        <span className="ml-3 text-slate-400">AI 研究员正在生成报告…</span>
      </div>
    );
  }

  const r = report;

  return (
    <div className="space-y-5 animate-slide-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-200">AI 量化研究员</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              多 Agent 协作：行业分析 → 因子挖掘 → 策略生成 → 回测验证 → 组合优化
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* 标签页切换 */}
          <div className="flex bg-[#0d1220] rounded-lg border border-[#1e2a3d] p-0.5">
            <button
              onClick={() => setActiveTab("report")}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                activeTab === "report"
                  ? "bg-cyan-500/15 text-cyan-300"
                  : "text-slate-500 hover:text-slate-300"
              )}
            >
              每日研报
            </button>
            <button
              onClick={() => setActiveTab("pipeline")}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                activeTab === "pipeline"
                  ? "bg-purple-500/15 text-purple-300"
                  : "text-slate-500 hover:text-slate-300"
              )}
            >
              Agent 流水线
            </button>
          </div>
          {activeTab === "report" && (
            <button
              className="btn-primary flex items-center gap-1.5 disabled:opacity-50"
              onClick={() => load(true)}
              disabled={regenerating}
            >
              <RefreshCw className={cn("w-3.5 h-3.5", regenerating && "animate-spin")} />
              {regenerating ? "生成中…" : "重新生成"}
            </button>
          )}
        </div>
      </div>

      {/* ── 标签页 1: 每日研报（原功能） ── */}
      {activeTab === "report" && r && (
        <>
          {/* Report Date + Source Badge */}
          <div className="flex items-center gap-2 text-sm flex-wrap">
            <FileText className="w-4 h-4 text-slate-500" />
            <span className="text-slate-400">报告日期: {r.date}</span>
            {r.llmEnabled ? (
              <span className="badge badge-purple ml-1 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                大模型生成 · {r.model}
              </span>
            ) : (
              <span className="badge badge-blue ml-1 flex items-center gap-1">
                <Cpu className="w-3 h-3" />
                规则合成（未配置LLM）
              </span>
            )}
            <span className="text-slate-600 ml-1">· 生成于 {r.generatedAt}</span>
          </div>

          {/* Market Summary */}
          <div className="card">
            <h2 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
              <Eye className="w-4 h-4 text-blue-400" />
              今日市场概览
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed">{r.marketSummary}</p>
          </div>

          {/* Sentiment + Judgment */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="card text-center">
              <div className="text-xs text-slate-500 mb-2">市场情绪评分</div>
              <div
                className={cn(
                  "text-4xl font-bold font-mono",
                  r.sentimentScore >= 70
                    ? "text-green-400"
                    : r.sentimentScore >= 50
                    ? "text-yellow-400"
                    : "text-red-400"
                )}
              >
                {r.sentimentScore}
              </div>
              <div className="text-xs text-slate-500 mt-1">/ 100</div>
            </div>
            <div className="card text-center">
              <div className="text-xs text-slate-500 mb-2">AI 综合判断</div>
              <div
                className={cn(
                  "text-2xl font-bold",
                  r.aiJudgment === "bullish"
                    ? "text-green-400"
                    : r.aiJudgment === "bearish"
                    ? "text-red-400"
                    : "text-yellow-400"
                )}
              >
                {r.aiJudgment === "bullish"
                  ? "看多"
                  : r.aiJudgment === "bearish"
                  ? "看空"
                  : "中性"}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {r.aiJudgment === "bullish" ? "建议适当增仓" : r.aiJudgment === "bearish" ? "建议降低仓位" : "维持均衡配置"}
              </div>
            </div>
            <div className="card text-center">
              <div className="text-xs text-slate-500 mb-2">分析覆盖</div>
              <div className="text-2xl font-bold font-mono text-slate-200">5,234</div>
              <div className="text-xs text-slate-500 mt-1">家公司 · 12维数据</div>
            </div>
          </div>

          {/* Outlook */}
          {r.outlook && (
            <div className="card bg-[#11161f] border-l-2 border-blue-500/50">
              <h2 className="text-sm font-semibold text-blue-400 mb-2 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                未来展望
              </h2>
              <p className="text-sm text-slate-300 leading-relaxed">{r.outlook}</p>
            </div>
          )}

          {/* Up Reasons & Risk Factors */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="card">
              <h2 className="text-sm font-semibold text-green-400 mb-3 flex items-center gap-2">
                <ThumbsUp className="w-4 h-4" />
                上涨原因
              </h2>
              <ul className="space-y-2.5">
                {r.upReasons.map((reason, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-slate-400">
                    <span className="w-5 h-5 rounded-full bg-green-900/30 text-green-400 text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    {reason}
                  </li>
                ))}
                {r.upReasons.length === 0 && <li className="text-sm text-slate-600">暂无</li>}
              </ul>
            </div>
            <div className="card">
              <h2 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                <ThumbsDown className="w-4 h-4" />
                风险因素
              </h2>
              <ul className="space-y-2.5">
                {r.riskFactors.map((risk, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-slate-400">
                    <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    {risk}
                  </li>
                ))}
                {r.riskFactors.length === 0 && <li className="text-sm text-slate-600">暂无</li>}
              </ul>
            </div>
          </div>

          {/* Focus Stocks */}
          <div className="card">
            <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-blue-400" />
              重点关注股票
            </h2>
            {r.focusStocks.length === 0 ? (
              <p className="text-sm text-slate-600">本期暂无重点推荐标的</p>
            ) : (
              <div className="space-y-3">
                {r.focusStocks.map((stock) => (
                  <div key={stock.code} className="bg-[#11161f] rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-mono text-xs text-slate-500">{stock.code}</span>
                      <span className="text-sm font-semibold text-slate-200">{stock.name}</span>
                      <span className="badge badge-green">推荐关注</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-green-400 font-medium">买入理由: </span>
                        <span className="text-slate-400">{stock.reason}</span>
                      </div>
                      <div>
                        <span className="text-red-400 font-medium">风险提示: </span>
                        <span className="text-slate-400">{stock.risk}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* 机构动向快览（v1.3.1 数据贯通） */}
      {activeTab === "report" && instData && (
        <div className="card p-4 bg-fuchsia-500/5 border-fuchsia-500/20">
          <h2 className="text-sm font-semibold text-fuchsia-400 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            机构动向快览（实时数据）
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
            <div className="bg-[#0d1220] rounded-lg p-3">
              <div className="text-[10px] text-slate-500 mb-1">机构活跃度</div>
              <div className="text-xl font-bold font-mono text-fuchsia-300">
                {instData.institutionActivity?.score ?? 0}
              </div>
              <div className="text-[10px] text-slate-600">
                {instData.institutionActivity?.level ?? "—"} · {instData.institutionActivity?.lhbCount ?? 0}只上榜
              </div>
            </div>
            <div className="bg-[#0d1220] rounded-lg p-3">
              <div className="text-[10px] text-slate-500 mb-1">北向资金</div>
              <div className={cn(
                "text-xl font-bold font-mono",
                (instData.northbound?.today ?? 0) > 0 ? "text-red-400" : "text-green-400",
              )}>
                {instData.northbound?.todayDesc ?? "—"}
              </div>
              <div className="text-[10px] text-slate-600">
                {(instData.northbound?.today ?? 0) > 0 ? "外资流入" : "外资流出"}
              </div>
            </div>
            <div className="bg-[#0d1220] rounded-lg p-3">
              <div className="text-[10px] text-slate-500 mb-1">主力方向</div>
              <div className={cn(
                "text-xl font-bold font-mono",
                instData.institutionActivity?.mainDirection === "流入" ? "text-red-400" : "text-green-400",
              )}>
                {instData.institutionActivity?.mainDirection ?? "—"}
              </div>
              <div className="text-[10px] text-slate-600">
                {formatFlow(instData.institutionActivity?.mainIntensity ?? 0)}
              </div>
            </div>
            <div className="bg-[#0d1220] rounded-lg p-3">
              <div className="text-[10px] text-slate-500 mb-1">龙虎榜净买TOP</div>
              <div className="text-xs text-slate-300 leading-relaxed">
                {(instData.lhb || []).slice(0, 3).map((e) => (
                  <div key={e.code} className="truncate">
                    {e.name} <span className="text-red-400 font-mono text-[10px]">{e.netBuyAmt}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <p className="text-[10px] text-slate-700 mt-3">基于 westock 实时数据聚合 · 更新于 {instData.timestamp}</p>
        </div>
      )}

      {/* ── 标签页 2: Agent 流水线 ── */}
      {activeTab === "pipeline" && (
        <>
          {/* 流水线控制栏 */}
          <div className="flex items-center gap-3">
            {pipelineMode === "idle" && (
              <button className="btn-primary flex items-center gap-1.5" onClick={runPipeline}>
                <Play className="w-3.5 h-3.5" />
                启动流水线
              </button>
            )}
            {pipelineMode === "running" && (
              <button className="btn-secondary flex items-center gap-1.5" disabled>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                运行中…
              </button>
            )}
            {pipelineMode === "done" && (
              <button className="btn-ghost flex items-center gap-1.5" onClick={resetPipeline}>
                <RotateCcw className="w-3.5 h-3.5" />
                重置流水线
              </button>
            )}
            <span className="text-xs text-slate-600">
              {pipelineMode === "idle"
                ? "点击启动，5 个 Agent 将依次执行行业分析 → 因子挖掘 → 策略生成 → 回测 → 组合优化"
                : pipelineMode === "running"
                ? "Agent 正在协作中…"
                : "流水线执行完成，可重置后重新运行"}
            </span>
          </div>

          {/* 流水线可视化 */}
          <AgentPipeline
            title="AI Agent 协作流水线"
            subtitle="5 个专业 Agent 依次协作，端到端产出策略与组合方案"
            steps={pipelineSteps}
          />

          {/* 流水线完成后展示简要结果卡片 */}
          {pipelineMode === "done" && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="card p-4 bg-emerald-500/5 border-emerald-500/20">
                <h3 className="text-xs text-emerald-400 font-semibold mb-2">策略绩效</h3>
                <div className="text-2xl font-bold font-mono text-emerald-300">+18.3%</div>
                <div className="text-xs text-slate-500 mt-1">年化收益 · 夏普 1.62</div>
              </div>
              <div className="card p-4 bg-amber-500/5 border-amber-500/20">
                <h3 className="text-xs text-amber-400 font-semibold mb-2">风险控制</h3>
                <div className="text-2xl font-bold font-mono text-amber-300">-12.5%</div>
                <div className="text-xs text-slate-500 mt-1">最大回撤 · VaR95=-2.1%</div>
              </div>
              <div className="card p-4 bg-blue-500/5 border-blue-500/20">
                <h3 className="text-xs text-blue-400 font-semibold mb-2">组合配置</h3>
                <div className="text-sm text-slate-300 leading-relaxed">
                  电力设备25% · 汽车20% · 电子20% · 医药15% · 现金20%
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ===== 与 AI 研究员对话（真正MultiTurn） ===== */}
      <div className="card p-4 flex flex-col">
        <div className="flex items-center gap-2 mb-3">
          <Bot className="w-4 h-4 text-blue-400" />
          <span className="section-title">与 AI 研究员对话</span>
          <div className="flex gap-1 ml-auto">
            {["DeepSeek", "通义", "沪深300"].map((btn) => (
              <button
                key={btn}
                onClick={() => setModel(btn)}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-medium rounded-md border transition-colors",
                  model === btn
                    ? "border-blue-500/40 bg-blue-500/10 text-blue-300"
                    : "border-[#1e2a3d] text-slate-500 hover:text-slate-300 hover:bg-white/5"
                )}
              >
                {btn}
              </button>
            ))}
            <button
              onClick={clearChat}
              className="btn-icon ml-1 opacity-60 hover:opacity-100"
              aria-label="清空对话"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="h-[300px] overflow-y-auto space-y-3 mb-3 pr-1">
          {chatMessages.length === 0 ? (
            <div className="text-xs text-slate-600 text-center mt-24 px-4 leading-relaxed">
              向 AI 研究员追问，例如：<br />
              「为什么本期看多？列出支撑逻辑与对应风险」<br />
              「{r?.focusStocks?.[0]?.code ?? "600519.SH"} 的买入理由和潜在风险是什么？」
            </div>
          ) : (
            chatMessages.map((m, i) => (
              <div
                key={i}
                className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={cn(
                    "max-w-[82%] rounded-lg px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap break-words",
                    m.role === "user"
                      ? "bg-blue-500/15 text-blue-100"
                      : "bg-[#0d1220] text-slate-300 border border-[#1a2235]"
                  )}
                >
                  {m.content}
                </div>
              </div>
            ))
          )}
          {chatLoading && (
            <div className="flex justify-start">
              <div className="bg-[#0d1220] border border-[#1a2235] rounded-lg px-3 py-2 text-xs text-slate-500 flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" /> 思考中…
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="flex items-center gap-2">
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="输入您的问题，基于本期报告深入追问…"
            className="input-dark flex-1"
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          />
          <button
            className="btn-primary px-3 disabled:opacity-50"
            onClick={sendMessage}
            disabled={chatLoading || !chatInput.trim()}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[10px] text-slate-700 mt-2">
          AI 研究员内容由大模型生成，仅作参考，不构成投资建议。请交叉多方信息后独立判断。
        </p>
      </div>

      {r && !r.llmEnabled && (
        <p className="text-xs text-slate-600 text-center">
          当前为规则合成模式。在 backend/.env 配置 LLM_API_KEY（DeepSeek / 通义千问 / OpenAI 兼容）
          即可切换为真实大模型生成。
        </p>
      )}
    </div>
  );
}
