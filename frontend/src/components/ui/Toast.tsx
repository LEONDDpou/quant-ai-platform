"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // 兜底：即使未挂载 Provider 也不报错（极端情况下降级为 no-op）
    return { toast: () => {} };
  }
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = Date.now() + Math.floor(Math.random() * 1000);
      setItems((prev) => [...prev, { id, message, type }]);
      setTimeout(() => remove(id), 2800);
    },
    [remove]
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 items-end pointer-events-none">
        {items.map((t) => {
          const Icon =
            t.type === "success" ? CheckCircle2 : t.type === "error" ? XCircle : Info;
          const color =
            t.type === "success"
              ? "text-emerald-400"
              : t.type === "error"
              ? "text-red-400"
              : "text-cyan-400";
          const border =
            t.type === "success"
              ? "border-emerald-500/30"
              : t.type === "error"
              ? "border-red-500/30"
              : "border-cyan-500/30";
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-center gap-2.5 bg-[#0f1626] border ${border} rounded-lg px-4 py-2.5 shadow-xl shadow-black/40 animate-slide-up min-w-[220px] max-w-[340px]`}
            >
              <Icon className={`w-4 h-4 flex-shrink-0 ${color}`} />
              <span className="text-xs text-slate-200 leading-snug flex-1">{t.message}</span>
              <button
                onClick={() => remove(t.id)}
                className="text-slate-600 hover:text-slate-300 transition-colors flex-shrink-0"
                aria-label="关闭"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
