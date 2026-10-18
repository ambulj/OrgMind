"use client";

import React, { useState, useEffect } from "react";
import { getAuthHeaders, defaultUserContext } from "@/lib/api";
import { Inbox, CheckCircle2, XCircle, AlertTriangle, ArrowRight, ShieldAlert, Users, Ticket, FolderGit2, RefreshCw } from "lucide-react";

interface ReviewItem {
  id: string;
  workspace_id: string;
  item_type: string;
  status: string;
  summary: string;
  payload: Record<string, any>;
  before_diff?: string | null;
  after_diff?: string | null;
  reviewed_by?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export default function ReviewQueuePage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [impactModalItem, setImpactModalItem] = useState<ReviewItem | null>(null);

  const loadReviews = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        status_filter: statusFilter,
        page_size: "50",
      });

      const res = await fetch(`/api/v1/reviews?${params.toString()}`, {
        headers: getAuthHeaders(defaultUserContext),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setItems(data.items || []);
    } catch (e: any) {
      setError(e.message || "Failed to load review items");
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (item: ReviewItem, action: "approve" | "reject") => {
    setActingId(item.id);
    setActionSuccess(null);
    try {
      const res = await fetch(`/api/v1/reviews/${item.id}/action`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(defaultUserContext),
        },
        body: JSON.stringify({ action }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err?.error?.message || `HTTP ${res.status}`);
      }

      const updatedItem: ReviewItem = await res.json();
      setActionSuccess(`Successfully ${action}d item ${item.id}`);

      // If approved and impact report exists, show impact summary modal
      if (action === "approve" && updatedItem.payload?.impact_report) {
        setImpactModalItem(updatedItem);
      }

      await loadReviews();
    } catch (e: any) {
      setError(e.message || `Failed to ${action} item`);
    } finally {
      setActingId(null);
    }
  };

  useEffect(() => {
    loadReviews();
  }, [statusFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Inbox className="h-5 w-5 text-blue-600" />
            Human-in-the-Loop Review Queue
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Review ambiguous entity resolutions, decision reversals, policy conflicts, and multi-hop impact trees.
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
          {["pending", "approved", "rejected", "all"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md capitalize transition ${
                statusFilter === st ? "bg-white text-blue-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {actionSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          {actionSuccess}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Review Queue Items List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-slate-400" />
            Loading review queue items...
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
            <Inbox className="h-10 w-10 text-slate-300 mx-auto mb-2" />
            No {statusFilter !== "all" ? statusFilter : ""} items currently in review queue.
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden p-5 space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
                    {item.id}
                  </span>
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                    {item.item_type}
                  </span>
                  <span className="text-xs text-slate-400">
                    {new Date(item.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-bold px-3 py-1 rounded-full border capitalize ${
                      item.status === "approved"
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : item.status === "rejected"
                        ? "bg-red-50 text-red-700 border-red-200"
                        : "bg-amber-50 text-amber-700 border-amber-200"
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
              </div>

              {/* Summary Description */}
              <div>
                <h3 className="text-sm font-bold text-slate-900">{item.summary}</h3>
                {item.reviewed_by && (
                  <p className="text-xs text-slate-500 mt-1">
                    Reviewed by <span className="font-semibold">{item.reviewed_by}</span> on{" "}
                    {item.reviewed_at ? new Date(item.reviewed_at).toLocaleString() : ""}
                  </p>
                )}
              </div>

              {/* Before vs After Diff Preview */}
              {(item.before_diff || item.after_diff) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="bg-red-50/50 p-3 rounded-lg border border-red-200">
                    <span className="font-bold text-red-800 block mb-1">Current Graph State (Before):</span>
                    <p className="text-slate-800 whitespace-pre-wrap">{item.before_diff || "None"}</p>
                  </div>
                  <div className="bg-emerald-50/50 p-3 rounded-lg border border-emerald-200">
                    <span className="font-bold text-emerald-800 block mb-1">Proposed Extraction (After):</span>
                    <p className="text-slate-800 whitespace-pre-wrap">{item.after_diff || "None"}</p>
                  </div>
                </div>
              )}

              {/* Existing Impact Analysis if already approved */}
              {item.payload?.impact_report && (
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
                  <span className="font-bold text-slate-700 block mb-1.5 flex items-center gap-1.5">
                    <ShieldAlert className="h-4 w-4 text-amber-600" />
                    Recorded Graph Impact on Approval:
                  </span>
                  <div className="flex flex-wrap gap-4 text-slate-600">
                    <span>
                      <strong className="text-slate-900">Affected Tickets:</strong>{" "}
                      {item.payload.impact_report.affected_tickets?.join(", ") || "None"}
                    </span>
                    <span>
                      <strong className="text-slate-900">Blocked Tickets:</strong>{" "}
                      {item.payload.impact_report.blocked_tickets?.join(", ") || "None"}
                    </span>
                    <span>
                      <strong className="text-slate-900">Responsible People:</strong>{" "}
                      {item.payload.impact_report.responsible_people?.join(", ") || "None"}
                    </span>
                  </div>
                </div>
              )}

              {/* Action Buttons for Pending Items */}
              {item.status === "pending" && (
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    onClick={() => handleAction(item, "reject")}
                    disabled={actingId === item.id}
                    className="px-3.5 py-1.5 bg-white hover:bg-red-50 text-red-700 border border-red-300 rounded-lg text-xs font-bold transition disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Reject
                  </button>
                  <button
                    onClick={() => handleAction(item, "approve")}
                    disabled={actingId === item.id}
                    className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {actingId === item.id ? "Applying..." : "Approve & Supersede"}
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Impact Modal for Just-Approved Items */}
      {impactModalItem && impactModalItem.payload?.impact_report && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full border border-slate-200 overflow-hidden">
            <div className="bg-emerald-600 px-5 py-4 text-white flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5" />
                <h3 className="font-bold text-sm">Decision Reversal Applied to Graph</h3>
              </div>
              <button
                onClick={() => setImpactModalItem(null)}
                className="text-emerald-100 hover:text-white"
              >
                &times;
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs">
              <p className="text-slate-600">
                The decision supersession has been committed to the knowledge graph. The following downstream entities were affected:
              </p>

              <div className="space-y-3">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-start gap-3">
                  <Ticket className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800">Affected Tickets:</span>
                    <div className="text-slate-600 mt-1 font-mono">
                      {impactModalItem.payload.impact_report.affected_tickets?.join(", ") || "No direct tickets"}
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-red-50 rounded-lg border border-red-200 flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-red-900">Blocked Tickets:</span>
                    <div className="text-red-700 mt-1 font-mono">
                      {impactModalItem.payload.impact_report.blocked_tickets?.join(", ") || "None"}
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-start gap-3">
                  <Users className="h-5 w-5 text-purple-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800">Responsible Owners to Notify:</span>
                    <div className="text-slate-600 mt-1 font-mono">
                      {impactModalItem.payload.impact_report.responsible_people?.join(", ") || "None"}
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-3 flex justify-end">
                <button
                  onClick={() => setImpactModalItem(null)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg font-bold text-xs"
                >
                  Close & Acknowledge
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
