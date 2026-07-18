"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchPortfolios,
  createPortfolio,
  updatePortfolio,
  deletePortfolio,
  runPortfolio,
  rebalancePortfolio,
  fetchPortfolioRebalances,
  type PortfolioResponse,
  type PortfolioRebalanceResponse,
  type PortfolioAllocation,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Layers,
  Play,
  RefreshCw,
  Plus,
  Trash2,
  Save,
} from "lucide-react";

export default function PortfolioPanel({
  accountId,
  onChanged,
}: {
  accountId: number | null;
  onChanged?: () => void;
}) {
  const [portfolios, setPortfolios] = useState<PortfolioResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedPf, setSelectedPf] = useState<number | null>(null);
  const [rebalances, setRebalances] = useState<PortfolioRebalanceResponse[]>([]);
  const [runResult, setRunResult] = useState<Record<string, string> | null>(null);
  // 编辑/新建表单
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editAlloc, setEditAlloc] = useState("");
  const [editCapital, setEditCapital] = useState("");

  const load = useCallback(async () => {
    if (accountId == null) return;
    setLoading(true);
    setError("");
    try {
      const pfs = await fetchPortfolios(accountId);
      setPortfolios(pfs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    load();
  }, [load]);

  const loadRebalances = async (pfId: number) => {
    try {
      const rbs = await fetchPortfolioRebalances(pfId);
      setRebalances(rbs);
    } catch {
      setRebalances([]);
    }
  };

  const handleSelect = (pf: PortfolioResponse) => {
    setSelectedPf(pf.id);
    setRunResult(null);
    loadRebalances(pf.id);
  };

  const handleCreate = () => {
    setEditId(null);
    setEditName("");
    setEditDesc("");
    setEditAlloc("");
    setEditCapital("");
  };

  const handleEdit = (pf: PortfolioResponse) => {
    setEditId(pf.id);
    setEditName(pf.name);
    setEditDesc(pf.description);
    setEditAlloc(JSON.stringify(
      pf.allocation.map((a) => ({ strategyId: a.strategyId, weight: a.weight }))
    ));
    setEditCapital(String(pf.totalCapital));
  };

  const handleSave = async () => {
    if (accountId == null || !editName.trim()) return;
    setLoading(true);
    let alloc: PortfolioAllocation[] = [];
    try {
      const parsed = JSON.parse(editAlloc || "[]");
      if (Array.isArray(parsed)) {
        alloc = parsed.map((a: { strategyId?: string; weight?: number }) => ({
          strategyId: a.strategyId || "",
          weight: a.weight || 0,
        })).filter((a) => a.strategyId);
      }
    } catch {
      alloc = [];
    }
    try {
      const body = {
        accountId,
        name: editName.trim(),
        description: editDesc.trim(),
        allocation: alloc,
        totalCapital: parseFloat(editCapital) || 0,
      };
      if (editId) {
        await updatePortfolio(editId, body);
      } else {
        await createPortfolio(body);
      }
      setEditId(null);
      load();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (pfId: number) => {
    try {
      await deletePortfolio(pfId);
      if (selectedPf === pfId) setSelectedPf(null);
      load();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const handleRun = async (pfId: number) => {
    setLoading(true);
    setRunResult(null);
    try {
      const res = await runPortfolio(pfId);
      setRunResult(res.strategyResults);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "运行失败");
    } finally {
      setLoading(false);
    }
  };

  const handleRebalance = async (pf: PortfolioResponse) => {
    if (accountId == null) return;
    setLoading(true);
    try {
      await rebalancePortfolio(pf.id, {
        accountId,
        name: pf.name,
        allocation: pf.allocation,
        totalCapital: pf.totalCapital,
      }, "手动再平衡");
      load();
      loadRebalances(pf.id);
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "再平衡失败");
    } finally {
      setLoading(false);
    }
  };

  const selectedPfData = portfolios.find((p) => p.id === selectedPf);

  return (
    <div className="card p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="section-title flex items-center gap-2">
          <Layers className="w-5 h-5" /> 策略组合管理
        </h2>
        <button
          className={cn("btn-primary text-sm flex items-center gap-1",
            !accountId && "opacity-50 cursor-not-allowed")}
          disabled={!accountId}
          onClick={handleCreate}
        >
          <Plus className="w-4 h-4" /> 新建组合
        </button>
      </div>

      {error && <div className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded">{error}</div>}

      {/* 编辑/新建表单 */}
      {editId !== null || editId === null && portfolios.some(() => true) === false
        ? null
        : null}
      {(editId !== null || portfolios.length === 0 || editId === null) && (editId !== null || portfolios.length === 0 || document.activeElement?.tagName === "INPUT") ? null : null}
      {/* 用简单条件 */}
      {(editId !== null || portfolios.length === 0) && (
        <div className="border border-blue-200 rounded-lg p-4 space-y-3 bg-blue-50/30">
          <h3 className="text-sm font-semibold text-blue-700">
            {editId ? "编辑组合" : "新建组合"}
          </h3>
          <input
            className="input w-full"
            placeholder="组合名称 *"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
          <input
            className="input w-full"
            placeholder="描述"
            value={editDesc}
            onChange={(e) => setEditDesc(e.target.value)}
          />
          <input
            className="input w-full"
            placeholder="分配总资金"
            type="number"
            value={editCapital}
            onChange={(e) => setEditCapital(e.target.value)}
          />
          <div>
            <label className="text-xs text-gray-500">策略分配 JSON（[{'{'}strategyId, weight{'}'}]）</label>
            <textarea
              className="input w-full font-mono text-xs mt-1"
              placeholder='[{"strategyId": "ai-xxx", "weight": 50}, {"strategyId": "ai-yyy", "weight": 50}]'
              rows={3}
              value={editAlloc}
              onChange={(e) => setEditAlloc(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <button className="btn-primary text-sm" onClick={handleSave} disabled={loading}>
              <Save className="w-3.5 h-3.5 inline mr-1" />保存
            </button>
            <button className="btn-ghost text-sm" onClick={() => setEditId(null)}>取消</button>
          </div>
        </div>
      )}

      {/* 组合列表 + 详情双栏 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 左栏：列表 */}
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {portfolios.length === 0 && (
            <div className="text-gray-400 text-xs py-8 text-center">暂无组合，点击"新建组合"创建</div>
          )}
          {portfolios.map((pf) => (
            <div
              key={pf.id}
              className={cn(
                "flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors hover:border-blue-300",
                selectedPf === pf.id && "border-blue-500 bg-blue-50/50",
              )}
              onClick={() => handleSelect(pf)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">{pf.name}</span>
                  <span className={cn("badge text-[10px]", pf.enabled ? "badge-green" : "badge-gray")}>
                    {pf.enabled ? "启用" : "停用"}
                  </span>
                </div>
                <div className="text-[10px] text-gray-400 mt-0.5">
                  {pf.strategyCount} 策略 · {pf.totalCapital.toLocaleString()} 元
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button className="btn-ghost text-xs p-1" onClick={(e) => { e.stopPropagation(); handleEdit(pf); }}>
                  ✏️
                </button>
                <button className="btn-ghost text-xs p-1 text-red-500" onClick={(e) => { e.stopPropagation(); handleDelete(pf.id); }}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* 右栏：选中组合的详情+操作 */}
        <div className="border rounded-lg p-4 min-h-[200px] space-y-3">
          {!selectedPfData ? (
            <div className="text-gray-400 text-xs py-8 text-center">选择一个组合查看详情</div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm">{selectedPfData.name}</h3>
                <div className="flex gap-2">
                  <button
                    className="btn-primary text-[10px] px-2 py-1"
                    onClick={() => handleRun(selectedPfData.id)}
                    disabled={loading}
                  >
                    <Play className="w-3 h-3 inline mr-1" />运行
                  </button>
                  <button
                    className="btn-ghost text-[10px] px-2 py-1"
                    onClick={() => handleRebalance(selectedPfData)}
                    disabled={loading}
                  >
                    <RefreshCw className="w-3 h-3 inline mr-1" />再平衡
                  </button>
                </div>
              </div>
              <div className="text-xs text-gray-500">{selectedPfData.description || "暂无描述"}</div>
              <div className="text-xs text-gray-400">
                资金: {selectedPfData.totalCapital.toLocaleString()} 元 · {selectedPfData.strategyCount} 个策略
              </div>

              {/* 策略分配列表 */}
              {selectedPfData.allocation.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-gray-600 mb-1">策略分配</div>
                  <div className="space-y-1">
                    {selectedPfData.allocation.map((a) => (
                      <div key={a.strategyId} className="flex items-center justify-between text-xs px-2 py-1 bg-gray-50 rounded">
                        <span className="font-mono text-[10px] truncate">{a.strategyId.slice(0, 16)}...</span>
                        <span className="font-semibold">{a.weight}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 运行结果 */}
              {runResult && (
                <div>
                  <div className="text-xs font-semibold text-gray-600 mb-1">运行结果</div>
                  <div className="text-[10px] space-y-0.5">
                    {Object.entries(runResult).map(([sid, status]) => (
                      <div key={sid} className={cn("px-2 py-0.5 rounded", status === "ok" ? "text-green-600" : "text-red-500")}>
                        {sid.slice(0, 12)}...: {status}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 再平衡历史 */}
              {rebalances.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-gray-600 mb-1">再平衡历史</div>
                  <div className="space-y-1 max-h-28 overflow-y-auto">
                    {rebalances.slice(0, 5).map((rb) => (
                      <div key={rb.id} className="flex items-center justify-between text-[10px] px-2 py-1 bg-gray-50 rounded">
                        <span>{rb.reason}</span>
                        <span className="text-gray-400">{rb.triggeredAt.slice(0, 16)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {loading && (
        <div className="flex justify-center py-2">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-400 border-t-transparent" />
        </div>
      )}
    </div>
  );
}
