"use client";

import React, { useState, useEffect } from "react";
import { getAuthHeaders, defaultUserContext } from "@/lib/api";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, RefreshCw, Clock, Database, ArrowUpCircle } from "lucide-react";

interface IngestionJob {
  id: string;
  workspace_id: string;
  connector_type: string;
  source_uri: string;
  status: string;
  items_processed: number;
  items_failed: number;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export default function IngestionPage() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [syncUpload, setSyncUpload] = useState<boolean>(true);

  const loadJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/ingestion/jobs?page_size=25", {
        headers: getAuthHeaders(defaultUserContext),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setJobs(data.items || []);
    } catch (e: any) {
      setError(e.message || "Failed to load ingestion jobs");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch(`/api/v1/ingestion/upload?sync=${syncUpload}`, {
        method: "POST",
        headers: {
          ...getAuthHeaders(defaultUserContext),
        },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err?.error?.message || `HTTP ${res.status}`);
      }

      const jobData = await res.json();
      setSuccessMsg(`File uploaded successfully! Created Job: ${jobData.id} (${jobData.status})`);
      setSelectedFile(null);
      await loadJobs();
    } catch (e: any) {
      setError(e.message || "Failed to upload file");
    } finally {
      setUploading(false);
    }
  };

  const triggerSampleData = async () => {
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await fetch("/api/v1/ingestion/jobs?sync=true", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(defaultUserContext),
        },
        body: JSON.stringify({
          connector_type: "sample_data",
          source_uri: "packages/core/orgmind/ingest/sample_northwind.json",
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const jobData = await res.json();
      setSuccessMsg(`Sample data ingestion completed! Job ${jobData.id}`);
      await loadJobs();
    } catch (e: any) {
      setError(e.message || "Failed to trigger sample connector");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <UploadCloud className="h-5 w-5 text-blue-600" />
            Document Ingestion & Connectors
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Ingest structured & unstructured documents (.md, .txt, .pdf) through the 8-stage retryable pipeline.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={triggerSampleData}
            disabled={loading || uploading}
            className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold transition flex items-center gap-1.5"
          >
            <Database className="h-4 w-4" />
            Trigger Sample Seed
          </button>
          <button
            onClick={loadJobs}
            disabled={loading}
            className="px-3.5 py-2 bg-white hover:bg-slate-50 text-blue-600 border border-slate-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          {successMsg}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600" />
          {error}
        </div>
      )}

      {/* Upload Box */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
          <ArrowUpCircle className="h-4 w-4 text-blue-600" />
          Upload Document (.md, .txt, .pdf)
        </h2>

        <form onSubmit={handleFileUpload} className="space-y-4">
          <div className="border-2 border-dashed border-slate-300 hover:border-blue-500 rounded-xl p-8 text-center bg-slate-50/50 transition">
            <UploadCloud className="h-10 w-10 text-slate-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-slate-700">
              Drag and drop your file here, or click to browse
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Supports Markdown (.md), Plain Text (.txt), and PDF documents (.pdf)
            </p>
            <input
              type="file"
              accept=".md,.txt,.pdf"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="mt-4 text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="syncUpload"
                checked={syncUpload}
                onChange={(e) => setSyncUpload(e.target.checked)}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="syncUpload" className="text-xs text-slate-600">
                Run synchronously (immediate graph commit feedback)
              </label>
            </div>

            <button
              type="submit"
              disabled={!selectedFile || uploading}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition disabled:opacity-50 flex items-center gap-2"
            >
              {uploading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
              {uploading ? "Ingesting Pipeline..." : "Upload & Ingest"}
            </button>
          </div>
        </form>
      </div>

      {/* Ingestion Jobs History */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Recent Ingestion Jobs ({jobs.length})
          </span>
          <span className="text-xs text-slate-400 font-mono">Queue: arq + redis 6380</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 uppercase font-semibold">
              <tr>
                <th className="p-3">Job ID</th>
                <th className="p-3">Connector</th>
                <th className="p-3">Source URI</th>
                <th className="p-3">Status</th>
                <th className="p-3">Processed</th>
                <th className="p-3">Created</th>
                <th className="p-3">Completed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-400 font-sans">
                    No ingestion jobs recorded yet.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50">
                    <td className="p-3 font-bold text-slate-900">{job.id}</td>
                    <td className="p-3 text-slate-700 font-sans">{job.connector_type}</td>
                    <td className="p-3 text-slate-600 truncate max-w-xs" title={job.source_uri}>
                      {job.source_uri}
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-sans border ${
                          job.status === "completed"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : job.status === "failed"
                            ? "bg-red-50 text-red-700 border-red-200"
                            : "bg-blue-50 text-blue-700 border-blue-200"
                        }`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="p-3 text-slate-700">
                      {job.items_processed} items ({job.items_failed} failed)
                    </td>
                    <td className="p-3 text-slate-500 font-sans text-[11px]">
                      {job.created_at ? new Date(job.created_at).toLocaleTimeString() : "-"}
                    </td>
                    <td className="p-3 text-slate-500 font-sans text-[11px]">
                      {job.completed_at ? new Date(job.completed_at).toLocaleTimeString() : "-"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
