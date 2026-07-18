"use client";

import { cn } from "@/lib/utils";
import { Settings2, Check } from "lucide-react";
import { useState } from "react";

interface RiskConfigItem {
  key: string;
  label: string;
  value: string | number;
  editable?: boolean;
}

interface RiskConfigPanelProps {
  items: RiskConfigItem[];
  title?: string;
  className?: string;
  onChange?: (key: string, value: string) => void;
}

export function RiskConfigPanel({ items, title = "风控参数配置", className, onChange }: RiskConfigPanelProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const beginEdit = (key: string, current: string | number) => {
    setEditingKey(key);
    setEditValue(String(current));
  };

  const commitEdit = () => {
    if (editingKey !== null && onChange) {
      onChange(editingKey, editValue);
    }
    setEditingKey(null);
  };

  return (
    <div className={cn("card p-4", className)}>
      <div className="flex items-center gap-2 mb-3">
        <Settings2 className="w-4 h-4 text-amber-400" />
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        <button
          onClick={() => {
            const first = items.find((i) => i.editable);
            if (first) beginEdit(first.key, first.value);
          }}
          className="btn-icon ml-auto opacity-50 hover:opacity-100"
          aria-label="编辑风控参数"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
        </button>
      </div>

      <div className="space-y-0">
        {items.map((item) => (
          <div
            key={item.key}
            className={cn(
              "flex items-center justify-between py-2 border-b last:border-b-0",
              "border-[#1a2235] hover:bg-white/[0.02]"
            )}
          >
            <span className="text-xs text-slate-400">{item.label}</span>
            {item.editable && editingKey === item.key ? (
              <input
                autoFocus
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                className="input-dark w-28 py-1 px-2 text-right"
                onBlur={commitEdit}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    commitEdit();
                  } else if (e.key === "Escape") {
                    e.preventDefault();
                    setEditingKey(null);
                  }
                }}
              />
            ) : (
              <button
                onClick={() => item.editable && beginEdit(item.key, item.value)}
                className={cn(
                  "font-mono text-sm flex items-center gap-1.5",
                  String(item.value).startsWith("-") ? "neg" : "pos",
                  item.editable && "cursor-pointer hover:text-cyan-400 transition-colors"
                )}
              >
                {typeof item.value === "number" && !String(item.value).includes("%") && !String(item.value).includes("$")
                  ? (item.value > 0 ? `+$${item.value.toLocaleString()}` : `$${Math.abs(item.value).toLocaleString()}`)
                  : item.value}
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Status indicator */}
      <div className="mt-3 pt-3 border-t border-[#1e2a3d]">
        <div className="flex items-center gap-2">
          <Check className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[11px] text-emerald-400">风控系统运行中</span>
        </div>
        <p className="text-[10px] text-slate-600 mt-1">所有交易均受风控规则约束</p>
      </div>
    </div>
  );
}
