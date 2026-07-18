"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  ListChecks,
  Plus,
  Trash2,
  RefreshCw,
  Settings2,
  Pin,
  PinOff,
  FileText,
  Radio,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchPaperPoolItems,
  addPaperPoolItem,
  updatePaperPoolItem,
  deletePaperPoolItem,
  fetchPaperPoolConfig,
  updatePaperPoolConfig,
  runPaperPoolMaintain,
  fetchPaperPoolChangelog,
  fetchPaperPoolSources,
  type PaperPoolItem,
  type PaperPoolConfig,
  type PaperPoolChangeLog,
  type PaperPoolSources,
  type PaperPoolHealth,
  type PaperPoolSyncSource,
  type PaperPoolMaintainResult,
} from "@/lib/api";

// 健康状态中文标签
const HEALTH_LABEL: Record<PaperPoolHealth, string> = {
  unknown: "未检测",
  ok: "正常",
  suspended: "停牌",
  st: "ST",
  illiquid: "流动性低",
};

const SYNC_SOURCE_LABEL: Record<PaperPoolSyncSource, string> = {
  manual: "手动维护",
  sector: "行业板块",
  concept: "概念板块",
  index: "指数",
};

// ============================================================
// 小组件
// ============================================================
function HealthBadge({ health }: { health: PaperPoolHealth }) {
  // 健康状态 → 徽章配色：ok=绿，unknown=灰，其余=红/黄
  const colorMap: Record<PaperPoolHealth, string> = {
    unknown: "badge badge-gray",
    ok: "badge badge-green",
    suspended: "badge badge-red",
    st: "badge badge-red",
    illiquid: "badge badge-yellow",
  };
  return <span className={colorMap[health] || "badge badge-gray"}>{HEALTH_LABEL[health] || health}</span>;
}

// ============================================================
// 主面板
// ============================================================
export default function StockPoolPanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [items, setItems] = useState<PaperPoolItem[]>([]);
  const [config, setConfig] = useState<PaperPoolConfig | null>(null);
  const [logs, setLogs] = useState<PaperPoolChangeLog[]>([]);
  const [sources, setSources] = useState<PaperPoolSources>({ sector: [], concept: [] });
  const [loading, setLoading] = useState(false);
  const [maintaining, setMaintaining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<PaperPoolMaintainResult | null>(null);

  // 添加表单
  const [addCode, setAddCode] = useState("");
  const [addName, setAddName] = useState("");
  const [addCategory, setAddCategory] = useState("");
  const [addPinned, setAddPinned] = useState(false);

  const loadAll = useCallback(async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      const [it, cf, lg, src] = await Promise.all([
        fetchPaperPoolItems(accountId),
        fetchPaperPoolConfig(accountId),
        fetchPaperPoolChangelog(accountId),
        fetchPaperPoolSources(),
      ]);
      setItems(it);
      setConfig(cf);
      setLogs(lg);
      setSources(src);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleAdd = async () => {
    if (!accountId) return;
    const code = addCode.trim();
    if (!code) {
      setError("请输入股票代码");
      return;
    }
    setError(null);
    try {
      await addPaperPoolItem(accountId, {
        code,
        name: addName.trim(),
        category: addCategory.trim(),
        pinned: addPinned,
      });
      setAddCode("");
      setAddName("");
      setAddCategory("");
      setAddPinned(false);
      await loadAll();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "添加失败");
    }
  };

  const handleRemove = async (item: PaperPoolItem) => {
    if (!accountId) return;
    try {
      await deletePaperPoolItem(accountId, item.id);
      await loadAll();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "移除失败");
    }
  };

  const handleTogglePin = async (item: PaperPoolItem) => {
    if (!accountId) return;
    try {
      await updatePaperPoolItem(accountId, item.id, { pinned: !item.pinned });
      await loadAll();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "更新失败");
    }
  };

  const handleSaveConfig = async () => {
    if (!accountId || !config) return;
    setError(null);
    try {
      await updatePaperPoolConfig(accountId, {
        autoSync: config.autoSync,
        syncSource: config.syncSource,
        syncName: config.syncSource === "manual" ? "" : config.syncName,
        removeSuspended: config.removeSuspended,
        removeSt: config.removeSt,
        removeIlliquid: config.removeIlliquid,
        minTurnover: config.minTurnover,
        maxSize: config.maxSize,
      });
      await loadAll();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "保存失败");
    }
  };

  const handleMaintain = async () => {
    if (!accountId) return;
    setMaintaining(true);
    setError(null);
    setLastResult(null);
    try {
      const res = await runPaperPoolMaintain(accountId);
      setLastResult(res);
      await loadAll();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "维护失败");
    } finally {
      setMaintaining(false);
    }
  };

  const sourceOptions =
    config?.syncSource === "concept" ? sources.concept : sources.sector;

  return (
    <div className="card">
      <div className="section-title flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Layers size={18} /> 股票池自动维护 (M179)
        </span>
        <span className="flex items-center gap-2">
          <span
            className={cn(
              "badge flex items-center gap-1",
              config?.autoSync ? "badge-green" : "badge-gray",
            )}
          >
            <Radio size={12} />
            {config?.autoSync ? "自动维护中 (每5分钟)" : "手动模式"}
          </span>
          <button
            className="btn btn-sm btn-primary flex items-center gap-1"
            onClick={handleMaintain}
            disabled={maintaining || !accountId}
          >
            <RefreshCw size={14} className={maintaining ? "animate-spin" : ""} />
            {maintaining ? "维护中…" : "立即维护"}
          </button>
        </span>
      </div>

      {error && <div className="alert alert-error mb-3">{error}</div>}
      {lastResult && (
        <div className="alert alert-info mb-3">
          本次维护：检测 {lastResult.checked} 只，新增 {lastResult.added} 只，
          移除 {lastResult.removed} 只，锁定跳过 {lastResult.skippedPinned} 只
        </div>
      )}
      {loading && <div className="text-sm text-gray-400 mb-2">加载中…</div>}

      {/* —— 区块1：股票池列表 —— */}
      <div className="mb-5">
        <div className="subsection-title flex items-center gap-2 mb-2">
          <ListChecks size={15} /> 股票池标的 ({items.length})
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>分组</th>
                <th>来源</th>
                <th>健康</th>
                <th>锁定</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-gray-400 py-4">
                    股票池为空，请在下方添加或开启自动同步
                  </td>
                </tr>
              )}
              {items.map((it) => (
                <tr key={it.id}>
                  <td className="font-mono">{it.code}</td>
                  <td>{it.name || "—"}</td>
                  <td>{it.category || "—"}</td>
                  <td className="text-gray-400">{it.source}</td>
                  <td>
                    <HealthBadge health={it.health} />
                  </td>
                  <td>
                    <button
                      className="btn btn-xs btn-ghost"
                      onClick={() => handleTogglePin(it)}
                      title={it.pinned ? "点击取消锁定" : "点击锁定(不被自动移除)"}
                    >
                      {it.pinned ? <Pin size={14} className="text-yellow-400" /> : <PinOff size={14} />}
                    </button>
                  </td>
                  <td>
                    <button className="btn btn-xs btn-danger" onClick={() => handleRemove(it)}>
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* —— 区块2：添加标的 —— */}
      <div className="mb-5">
        <div className="subsection-title flex items-center gap-2 mb-2">
          <Plus size={15} /> 添加标的
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="form-field">
            <label>代码</label>
            <input
              className="input-sm"
              placeholder="如 600519"
              value={addCode}
              onChange={(e) => setAddCode(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label>名称</label>
            <input
              className="input-sm"
              placeholder="可选"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label>分组</label>
            <input
              className="input-sm"
              placeholder="如 核心仓"
              value={addCategory}
              onChange={(e) => setAddCategory(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={addPinned} onChange={(e) => setAddPinned(e.target.checked)} />
            锁定
          </label>
          <button className="btn btn-sm btn-primary" onClick={handleAdd}>
            添加
          </button>
        </div>
      </div>

      {/* —— 区块3：自动维护配置 —— */}
      {config && (
        <div className="mb-5">
          <div className="subsection-title flex items-center gap-2 mb-2">
            <Settings2 size={15} /> 自动维护配置
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={config.autoSync}
                onChange={(e) => setConfig({ ...config, autoSync: e.target.checked })}
              />
              启用板块自动同步（按板块成分自动增删）
            </label>
            <div className="form-field">
              <label>同步源</label>
              <select
                className="input-sm"
                value={config.syncSource}
                onChange={(e) =>
                  setConfig({ ...config, syncSource: e.target.value as PaperPoolSyncSource, syncName: "" })
                }
              >
                {(Object.keys(SYNC_SOURCE_LABEL) as PaperPoolSyncSource[]).map((s) => (
                  <option key={s} value={s}>
                    {SYNC_SOURCE_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>
            {config.syncSource !== "manual" && (
              <div className="form-field">
                <label>跟踪板块</label>
                <select
                  className="input-sm"
                  value={config.syncName}
                  onChange={(e) => setConfig({ ...config, syncName: e.target.value })}
                >
                  <option value="">— 请选择 —</option>
                  {sourceOptions.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="form-field">
              <label>池容量上限 (0=不限)</label>
              <input
                className="input-sm"
                type="number"
                min={0}
                value={config.maxSize}
                onChange={(e) => setConfig({ ...config, maxSize: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={config.removeSuspended}
                onChange={(e) => setConfig({ ...config, removeSuspended: e.target.checked })}
              />
              自动移除停牌
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={config.removeSt}
                onChange={(e) => setConfig({ ...config, removeSt: e.target.checked })}
              />
              自动移除 ST/*ST
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={config.removeIlliquid}
                onChange={(e) => setConfig({ ...config, removeIlliquid: e.target.checked })}
              />
              自动移除流动性不足
            </label>
            <div className="form-field">
              <label>最小换手率(%)</label>
              <input
                className="input-sm w-20"
                type="number"
                step={0.1}
                min={0}
                value={config.minTurnover}
                onChange={(e) => setConfig({ ...config, minTurnover: Number(e.target.value) })}
              />
            </div>
          </div>
          <button className="btn btn-sm btn-primary mt-3" onClick={handleSaveConfig}>
            保存配置
          </button>
        </div>
      )}

      {/* —— 区块4：变更日志 —— */}
      <div>
        <div className="subsection-title flex items-center gap-2 mb-2">
          <FileText size={15} /> 变更日志
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>代码</th>
                <th>动作</th>
                <th>原因</th>
                <th>来源</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center text-gray-400 py-3">
                    暂无变更记录
                  </td>
                </tr>
              )}
              {logs.map((l) => (
                <tr key={l.id}>
                  <td className="text-gray-400">{l.createdAt?.slice(0, 19) || "—"}</td>
                  <td className="font-mono">{l.code || "—"}</td>
                  <td>
                    <span
                      className={cn(
                        "badge",
                        l.action === "add" ? "badge-green" : "badge-red",
                      )}
                    >
                      {l.action === "add" ? "新增" : "移除"}
                    </span>
                  </td>
                  <td>{l.reason || "—"}</td>
                  <td className="text-gray-400">{l.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
