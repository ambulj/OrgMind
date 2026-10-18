"use client";

import React, { useState, useEffect } from "react";
import { getAuthHeaders, defaultUserContext } from "@/lib/api";
import { GitFork, Search, Clock, ArrowRight, ShieldCheck, FileText, CheckCircle2, AlertCircle, History } from "lucide-react";

interface DecisionItem {
  id: string;
  name: string;
  type: string;
  properties: {
    text?: string;
    topic?: string;
    status?: string;
    valid_from?: string;
    valid_to?: string;
    confidence?: number;
    [key: string]: any;
  };
}

interface LineageData {
  decision_id: string;
  topic: string;
  status: string;
  valid_from?: string;
  valid_to?: string;
  superseded_by?: string;
  supersedes?: string;
  source_anchors: Array<{
    source_id: string;
    file_path?: string;
    content_hash?: string;
  }>;
  lineage_chain: Array<{
    relation: string;
    decision_id: string;
    text?: string;
  }>;
}

export default function DecisionLineagePage() {
  const [decisions, setDecisions] = useState<DecisionItem[]>([]);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [lineage, setLineage] = useState<LineageData | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [loadingList, setLoadingList] = useState<boolean>(false);
  const [loadingLineage, setLoadingLineage] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch decisions list
  const loadDecisions = async (search: string = "") => {
    setLoadingList(true);
    setError(null);
    try {
      const params = new URLSearchParams({ page_size: "50" });
      if (search) params.set("search", search);

      const res = await fetch(`/api/v1/entities/decisions?${params.toString()}`, {
        headers: getAuthHeaders(defaultUserContext),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDecisions(data.items || []);

      if (data.items?.length > 0 && !selectedDecisionId) {
        selectDecision(data.items[0].id);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load decisions list");
    } finally {
      setLoadingList(false);
    }
  };

  // Fetch lineage for selected decision
  const selectDecision = async (id: string) => {
    setSelectedDecisionId(id);
    setLoadingLineage(true);
    try {
      const res = await fetch(`/api/v1/decisions/${id}/lineage`, {
        headers: getAuthHeaders(defaultUserContext),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLineage(data);
    } catch (e: any) {
      setError(e.message || `Failed to fetch lineage for ${id}`);
    } finally {
      setLoadingLineage(false);
    }
  };

  useEffect(() => {
    loadDecisions();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <GitFork className="h-5 w-5 text-blue-600" />
            Decision Lineage & Supersession Tree
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Trace bitemporal governance records, active vs. superseded states, validity dates, and source anchors.
          </p>
        </div>

        {/* Search */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            loadDecisions(searchTerm);
          }}
          className="relative w-full md:w-72"
        >
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search topic or ID..."
            className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </form>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Decisions Catalog */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[700px]">
          <div className="p-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Decisions Catalog ({decisions.length})
            </span>
            <button
              onClick={() => loadDecisions(searchTerm)}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {loadingList ? (
              <div className="p-8 text-center text-slate-400 text-sm">Loading decisions...</div>
            ) : decisions.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">No decisions found.</div>
            ) : (
              decisions.map((d) => {
                const isSelected = d.id === selectedDecisionId;
                const status = d.properties.status || "current";
                const isSuperseded = status === "superseded" || Boolean(d.properties.valid_to);

                return (
                  <button
                    key={d.id}
                    onClick={() => selectDecision(d.id)}
                    className={`w-full text-left p-4 transition flex flex-col gap-1.5 ${
                      isSelected
                        ? "bg-blue-50/70 border-l-4 border-blue-600"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-slate-800">{d.id}</span>
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                          isSuperseded
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : "bg-emerald-50 text-emerald-700 border-emerald-200"
                        }`}
                      >
                        {isSuperseded ? "Superseded" : "Active"}
                      </span>
                    </div>

                    <div className="text-sm font-semibold text-slate-900 line-clamp-1">
                      {d.properties.topic || d.name}
                    </div>

                    <p className="text-xs text-slate-500 line-clamp-2">
                      {d.properties.text || "No text description"}
                    </p>

                    <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400">
                      <Clock className="h-3 w-3" />
                      <span>From: {d.properties.valid_from ? d.properties.valid_from.slice(0, 10) : "Initial"}</span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right: Detailed Lineage View */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm p-6 overflow-y-auto h-[700px]">
          {loadingLineage ? (
            <div className="h-full flex items-center justify-center text-slate-400 text-sm">
              Loading lineage chain...
            </div>
          ) : !lineage ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-slate-400">
              <History className="h-12 w-12 text-slate-300 mb-2" />
              <p className="text-sm">Select a decision from the left panel to inspect its supersession chain and source proof.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Selected Decision Header Card */}
              <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-blue-700 bg-blue-100/60 px-2.5 py-1 rounded border border-blue-200">
                      {lineage.decision_id}
                    </span>
                    <span className="text-sm font-bold text-slate-900">{lineage.topic}</span>
                  </div>

                  <span
                    className={`text-xs font-bold px-3 py-1 rounded-full border ${
                      lineage.status === "superseded"
                        ? "bg-amber-100 text-amber-800 border-amber-300"
                        : "bg-emerald-100 text-emerald-800 border-emerald-300"
                    }`}
                  >
                    {lineage.status.toUpperCase()}
                  </span>
                </div>

                {/* Bitemporal Validity Interval */}
                <div className="grid grid-cols-2 gap-4 mt-4 text-xs bg-white p-3 rounded-lg border border-slate-200">
                  <div>
                    <span className="font-semibold text-slate-500">Real-World Valid From:</span>
                    <div className="font-mono text-slate-800 mt-0.5">{lineage.valid_from || "Record Origin"}</div>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-500">Real-World Valid To:</span>
                    <div className="font-mono text-slate-800 mt-0.5">{lineage.valid_to || "Present (Indefinite)"}</div>
                  </div>
                </div>
              </div>

              {/* Supersession Lineage Tree */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                  <GitFork className="h-4 w-4 text-blue-600" />
                  Supersession Lineage Path
                </h3>

                <div className="space-y-3">
                  {/* Previous Superseded Decision */}
                  {lineage.supersedes && (
                    <div className="flex items-start gap-3 p-4 bg-amber-50/60 rounded-xl border border-amber-200 text-xs">
                      <div className="p-2 bg-amber-100 text-amber-800 rounded-lg font-bold">PREVIOUS</div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-amber-900">{lineage.supersedes}</span>
                          <span className="text-amber-700 font-semibold">SUPERSEDED</span>
                        </div>
                        <p className="text-slate-600 mt-1">
                          {lineage.lineage_chain.find((c) => c.relation === "supersedes")?.text ||
                            "Prior policy superseded by this current decision."}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Current Active / Highlighted Node */}
                  <div className="p-4 bg-blue-50 rounded-xl border-2 border-blue-500 text-xs shadow-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-blue-900 text-sm">{lineage.decision_id}</span>
                      <span className="text-blue-700 font-bold px-2 py-0.5 bg-blue-100 rounded">SELECTED</span>
                    </div>
                    <p className="text-slate-800 mt-2 font-medium">
                      Topic: <span className="font-bold">{lineage.topic}</span>
                    </p>
                  </div>

                  {/* Future / Superseding Decision if replaced */}
                  {lineage.superseded_by && (
                    <div className="flex items-start gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                      <div className="p-2 bg-slate-200 text-slate-800 rounded-lg font-bold">SUPERSEDED BY</div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-slate-900">{lineage.superseded_by}</span>
                          <span className="text-emerald-700 font-semibold">ACTIVE REPLACEMENT</span>
                        </div>
                        <p className="text-slate-600 mt-1">
                          {lineage.lineage_chain.find((c) => c.relation === "superseded_by")?.text ||
                            "A subsequent decision reversed or superseded this policy."}
                        </p>
                      </div>
                    </div>
                  )}

                  {!lineage.supersedes && !lineage.superseded_by && (
                    <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-500 text-center">
                      This decision is the original baseline policy with no recorded supersessions.
                    </div>
                  )}
                </div>
              </div>

              {/* Source Anchors & Cryptographic Proof */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                  Cryptographic Source Anchors (Rule 4 & Rule 5)
                </h3>

                {lineage.source_anchors.length === 0 ? (
                  <p className="text-xs text-slate-400">No source anchors linked to this decision record.</p>
                ) : (
                  <div className="space-y-2">
                    {lineage.source_anchors.map((src) => (
                      <div key={src.source_id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-slate-900 flex items-center gap-1.5">
                            <FileText className="h-3.5 w-3.5 text-blue-600" />
                            {src.source_id}
                          </span>
                          <span className="text-[11px] text-slate-500 font-mono">{src.file_path || "graph_origin"}</span>
                        </div>

                        {src.content_hash && (
                          <div className="text-[10px] text-slate-500 font-mono break-all pt-1">
                            SHA-256 Hash: {src.content_hash}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
