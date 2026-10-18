"use client";

import React, { useState, useEffect } from "react";
import { getAuthHeaders, defaultUserContext } from "@/lib/api";
import { ShieldCheck, Search, Filter, RefreshCw, Eye, X, FileText, UserCheck, Clock } from "lucide-react";

interface AuditLogRecord {
  id: string;
  workspace_id: string;
  actor_id?: string | null;
  actor_email?: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before_state?: string | null;
  after_state?: string | null;
  reason?: string | null;
  timestamp: string;
}

export default function AuditLogPage() {
  const [records, setRecords] = useState<AuditLogRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [filterAction, setFilterAction] = useState<string>("");
  const [filterEntityType, setFilterEntityType] = useState<string>("");
  const [filterActor, setFilterActor] = useState<string>("");

  const [selectedRecord, setSelectedRecord] = useState<AuditLogRecord | null>(null);

  const loadAuditLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page_size: "50",
      });
      if (filterAction) params.set("action", filterAction.trim());
      if (filterEntityType) params.set("entity_type", filterEntityType.trim());
      if (filterActor) params.set("actor", filterActor.trim());

      const res = await fetch(`/api/v1/audit?${params.toString()}`, {
        headers: getAuthHeaders(defaultUserContext),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRecords(data.items || []);
      setTotal(data.total || 0);
    } catch (e: any) {
      setError(e.message || "Failed to load governance audit logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditLogs();
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-blue-600" />
            Immutable Governance Audit Log (Rule 4 & Rule 7)
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Tamper-evident record of all human approvals, decision reversals, proposed actions, and redaction tombstones.
          </p>
        </div>

        <button
          onClick={loadAuditLogs}
          disabled={loading}
          className="px-4 py-2 bg-white hover:bg-slate-50 text-blue-600 border border-slate-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5 self-start md:self-auto"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh Log
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            loadAuditLogs();
          }}
          className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end"
        >
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Actor Email / ID</label>
            <input
              type="text"
              value={filterActor}
              onChange={(e) => setFilterActor(e.target.value)}
              placeholder="e.g. admin@northwind.io"
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Action Name</label>
            <input
              type="text"
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              placeholder="e.g. approve_decision_reversal"
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Entity Type</label>
            <select
              value={filterEntityType}
              onChange={(e) => setFilterEntityType(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Entity Types</option>
              <option value="Decision">Decision</option>
              <option value="Source">Source</option>
              <option value="Action">Action</option>
              <option value="Ticket">Ticket</option>
            </select>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-1.5 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5"
            >
              <Filter className="h-3.5 w-3.5" />
              Apply Filters
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Audit Log Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Audit Records ({records.length} shown of {total})
          </span>
          <span className="text-xs text-slate-400 font-mono">Role Gate: Auditor or Admin</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 uppercase font-semibold">
              <tr>
                <th className="p-3">Log ID</th>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Actor</th>
                <th className="p-3">Action</th>
                <th className="p-3">Entity</th>
                <th className="p-3">Reason / Details</th>
                <th className="p-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {records.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-400">
                    No audit records matching criteria.
                  </td>
                </tr>
              ) : (
                records.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="p-3 font-mono text-[11px] font-bold text-slate-700">{r.id}</td>
                    <td className="p-3 text-slate-500 font-mono text-[11px]">
                      {new Date(r.timestamp).toLocaleString()}
                    </td>
                    <td className="p-3 font-medium text-slate-900">{r.actor_email || r.actor_id || "system"}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-blue-50 text-blue-700 border border-blue-200">
                        {r.action}
                      </span>
                    </td>
                    <td className="p-3 font-mono text-[11px] text-slate-800">
                      {r.entity_type}: {r.entity_id}
                    </td>
                    <td className="p-3 text-slate-600 max-w-sm truncate" title={r.reason || ""}>
                      {r.reason || "-"}
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setSelectedRecord(r)}
                        className="p-1 text-slate-400 hover:text-blue-600 transition"
                        title="View Full State Diffs"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Record State Inspection Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full border border-slate-200 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="bg-slate-900 px-5 py-4 text-white flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm">Audit Record Detail: {selectedRecord.id}</h3>
                <span className="text-[11px] text-slate-400 font-mono">
                  {selectedRecord.action} &bull; {selectedRecord.entity_type}:{selectedRecord.entity_id}
                </span>
              </div>
              <button
                onClick={() => setSelectedRecord(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs overflow-y-auto">
              <div className="grid grid-cols-2 gap-4 bg-slate-50 p-3 rounded-lg border border-slate-200">
                <div>
                  <span className="font-bold text-slate-500">Actor:</span>
                  <div className="font-mono text-slate-800">{selectedRecord.actor_email || selectedRecord.actor_id}</div>
                </div>
                <div>
                  <span className="font-bold text-slate-500">Recorded Timestamp:</span>
                  <div className="font-mono text-slate-800">{new Date(selectedRecord.timestamp).toISOString()}</div>
                </div>
              </div>

              <div>
                <span className="font-bold text-slate-700">Governance Reason / Justification:</span>
                <p className="mt-1 p-2.5 bg-slate-50 rounded border border-slate-200 text-slate-800 font-mono">
                  {selectedRecord.reason || "None recorded"}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="font-bold text-red-800 block mb-1">Before State:</span>
                  <pre className="p-3 bg-red-50/50 text-slate-800 rounded-lg border border-red-200 text-[11px] overflow-x-auto max-h-48 whitespace-pre-wrap font-mono">
                    {selectedRecord.before_state || "No prior state"}
                  </pre>
                </div>
                <div>
                  <span className="font-bold text-emerald-800 block mb-1">After State:</span>
                  <pre className="p-3 bg-emerald-50/50 text-slate-800 rounded-lg border border-emerald-200 text-[11px] overflow-x-auto max-h-48 whitespace-pre-wrap font-mono">
                    {selectedRecord.after_state || "No post state"}
                  </pre>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-slate-100 flex justify-end bg-slate-50">
              <button
                onClick={() => setSelectedRecord(null)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg font-bold text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
