"use client";

import { cn } from "@/lib/utils";
import {
  BarChart3,
  Beaker,
  Brain,
  CheckCircle2,
  ChevronRight,
  Cpu,
  FlaskConical,
  Loader2,
  PieChart,
  TrendingUp,
  XCircle,
} from "lucide-react";

export type AgentStatus = "idle" | "running" | "completed" | "failed";

export interface AgentStep {
  id: string;
  agentName: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  status: AgentStatus;
  duration?: string;
  output?: string;
  error?: string;
}

interface AgentPipelineProps {
  title: string;
  subtitle?: string;
  steps: AgentStep[];
  className?: string;
}

const statusIcon = (status: AgentStatus) => {
  switch (status) {
    case "running":
      return <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />;
    case "completed":
      return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    case "failed":
      return <XCircle className="w-4 h-4 text-red-400" />;
    default:
      return <div className="w-4 h-4 rounded-full border border-slate-600" />;
  }
};

const statusColor = (status: AgentStatus) => {
  switch (status) {
    case "running":
      return "border-cyan-500/50 bg-cyan-500/5";
    case "completed":
      return "border-emerald-500/30 bg-emerald-500/5";
    case "failed":
      return "border-red-500/30 bg-red-500/5";
    default:
      return "border-[#1e2a3d] bg-[#0d1220]";
  }
};

export function AgentPipeline({ title, subtitle, steps, className }: AgentPipelineProps) {
  return (
    <div className={cn("card p-4", className)}>
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-4 h-4 text-purple-400" />
        <span className="section-title">{title}</span>
        {subtitle && <span className="text-xs text-slate-600 ml-2">{subtitle}</span>}
      </div>

      <div className="relative">
        {/* 流水线连接线 */}
        <div className="absolute left-[19px] top-8 bottom-0 w-px bg-[#1e2a3d] hidden sm:block" />

        <div className="space-y-3">
          {steps.map((step, idx) => (
            <div key={step.id} className="relative">
              {/* Step card */}
              <div
                className={cn(
                  "border rounded-lg p-3 transition-all duration-300 ml-0 sm:ml-10",
                  statusColor(step.status)
                )}
              >
                <div className="flex items-start gap-3">
                  {/* Icon */}
                  <div
                    className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
                      step.status === "running"
                        ? "bg-cyan-500/10"
                        : step.status === "completed"
                        ? "bg-emerald-500/10"
                        : step.status === "failed"
                        ? "bg-red-500/10"
                        : "bg-slate-700/30"
                    )}
                  >
                    {step.icon}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={cn(
                          "text-xs font-semibold",
                          step.status === "running"
                            ? "text-cyan-300"
                            : step.status === "completed"
                            ? "text-emerald-300"
                            : step.status === "failed"
                            ? "text-red-300"
                            : "text-slate-500"
                        )}
                      >
                        {step.label}
                      </span>
                      <span className="text-[10px] text-slate-600 font-mono">{step.agentName}</span>
                      {step.status === "running" && (
                        <span className="badge badge-cyan ml-auto">运行中</span>
                      )}
                      {step.status === "completed" && step.duration && (
                        <span className="text-[10px] text-slate-600 font-mono ml-auto">{step.duration}</span>
                      )}
                      {step.status === "failed" && (
                        <span className="badge badge-red ml-auto">失败</span>
                      )}
                    </div>

                    <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">{step.description}</p>

                    {/* 输出摘要 */}
                    {step.output && step.status === "completed" && (
                      <div className="mt-2 p-2 bg-[#0d1220] rounded-md border border-[#1a2235] text-[11px] text-slate-400 leading-relaxed line-clamp-3">
                        {step.output}
                      </div>
                    )}

                    {/* 错误信息 */}
                    {step.error && step.status === "failed" && (
                      <div className="mt-2 p-2 bg-red-950/20 rounded-md border border-red-900/30 text-[11px] text-red-400">
                        {step.error}
                      </div>
                    )}
                  </div>

                  {/* Status indicator */}
                  <div className="flex-shrink-0">{statusIcon(step.status)}</div>
                </div>
              </div>

              {/* 连接箭头 (mobile only) */}
              {idx < steps.length - 1 && (
                <div className="flex justify-center py-1 sm:hidden">
                  <ChevronRight className="w-4 h-4 text-slate-700 rotate-90" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** 预置的 Agent 图标映射 */
export const AGENT_ICONS: Record<string, React.ReactNode> = {
  IndustryAnalyst: <BarChart3 className="w-4 h-4 text-blue-400" />,
  FactorEngineer: <Beaker className="w-4 h-4 text-purple-400" />,
  StrategyBuilder: <Cpu className="w-4 h-4 text-cyan-400" />,
  BacktestRunner: <FlaskConical className="w-4 h-4 text-amber-400" />,
  PortfolioOptimizer: <PieChart className="w-4 h-4 text-emerald-400" />,
};
