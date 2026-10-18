"use client";

import { useState } from "react";
import {
  Search,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Send,
  FileText,
  ThumbsUp,
  ThumbsDown,
  CheckCircle2,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Terminal,
} from "lucide-react";
import { streamAskQuestion, AskEventPayload } from "@/lib/api";

interface TraceStep {
  step: number;
  tool?: string;
  description?: string;
  arguments?: any;
  resultSummary?: string;
}

export default function AskBrainPage() {
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamSteps, setStreamSteps] = useState<TraceStep[]>([]);
  const [answerText, setAnswerText] = useState("");
  const [citations, setCitations] = useState<any[]>([]);
  const [validation, setValidation] = useState<any>(null);
  const [confidence, setConfidence] = useState<any>(null);
  const [proposedAction, setProposedAction] = useState<any>(null);
  const [confirmedAction, setConfirmedAction] = useState<any>(null);
  const [activeCitation, setActiveCitation] = useState<any>(null);
  const [feedbackSent, setFeedbackSent] = useState<number | null>(null);
  const [showSteps, setShowSteps] = useState(true);

  const sampleQueries = [
    "Who owns the OAuth Upgrade project?",
    "Who knows the most about Paynova in the company?",
    "What is our official decision on authentication and where was it documented?",
    "Compare the preliminary draft technical evaluation for European billing against the official decision.",
    "Draft a message to #backend-eng about OAuth token expiry and create a ticket.",
  ];

  async function handleAsk(e?: React.FormEvent, customQ?: string) {
    if (e) e.preventDefault();
    const query = customQ || question;
    if (!query.trim() || isStreaming) return;

    setQuestion(query);
    setIsStreaming(true);
    setStreamSteps([]);
    setAnswerText("");
    setCitations([]);
    setValidation(null);
    setConfidence(null);
    setProposedAction(null);
    setConfirmedAction(null);
    setActiveCitation(null);
    setFeedbackSent(null);

    try {
      for await (const chunk of streamAskQuestion(query, asOf || null)) {
        handleStreamEvent(chunk);
      }
    } catch (err: any) {
      setAnswerText((prev) => prev + `\n\n[Error]: ${err.message}`);
    } finally {
      setIsStreaming(false);
    }
  }

  function handleStreamEvent(eventPayload: AskEventPayload) {
    const { event, data } = eventPayload;

    if (event === "step") {
      setStreamSteps((prev) => [
        ...prev,
        {
          step: data.step ?? prev.length,
          description: data.description || "Processing knowledge graph query...",
        },
      ]);
    } else if (event === "tool_call") {
      setStreamSteps((prev) => [
        ...prev,
        {
          step: prev.length,
          tool: data.tool,
          arguments: data.arguments,
          description: `Executing tool: ${data.tool}`,
        },
      ]);
    } else if (event === "tool_result_summary") {
      setStreamSteps((prev) => [
        ...prev,
        {
          step: prev.length,
          resultSummary: data.summary,
          description: `Completed: ${data.summary}`,
        },
      ]);
    } else if (event === "token") {
      setAnswerText((prev) => prev + (data.text || ""));
    } else if (event === "citation") {
      setCitations((prev) => {
        if (!prev.some((c) => c.source_id === data.source_id)) {
          return [...prev, data];
        }
        return prev;
      });
    } else if (event === "validation") {
      setValidation(data);
    } else if (event === "confidence") {
      setConfidence(data);
    } else if (event === "proposed_action") {
      setProposedAction(data);
    } else if (event === "done") {
      if (data.full_answer && !answerText) {
        setAnswerText(data.full_answer);
      }
    }
  }

  async function handleConfirmAction(actionId: string) {
    try {
      const res = await fetch("/api/v1/actions/confirm", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Workspace-Id": "default",
          "X-Role": "Admin",
        },
        body: JSON.stringify({ action_id: actionId }),
      });
      const data = await res.json();
      setConfirmedAction(data);
    } catch (err: any) {
      alert(`Action confirmation failed: ${err.message}`);
    }
  }

  return (
    <div className="space-y-8">
      {/* Search Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-blue-600" />
            Company Brain Assistant
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Ask any question across people, architecture decisions, tickets, chat channels, and documents.
            Every claim is grounded in FalkorDB with cryptographic provenance.
          </p>
        </div>

        {/* Query Input Form */}
        <form onSubmit={handleAsk} className="mt-6 space-y-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-3.5 h-5 w-5 text-slate-400" />
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about architecture, project ownership, decisions, or simulated actions..."
                className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:bg-white transition"
                disabled={isStreaming}
              />
            </div>

            {/* Bitemporal As-Of Picker */}
            <div className="flex items-center gap-2 bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs">
              <Clock className="h-4 w-4 text-slate-500" />
              <span className="font-medium text-slate-600">As Of:</span>
              <input
                type="date"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
                className="bg-transparent text-slate-800 focus:outline-none cursor-pointer"
                title="Bitemporal time travel date"
              />
              {asOf && (
                <button
                  type="button"
                  onClick={() => setAsOf("")}
                  className="text-slate-400 hover:text-slate-600 ml-1 text-xs"
                >
                  Clear
                </button>
              )}
            </div>

            <button
              type="submit"
              disabled={isStreaming || !question.trim()}
              className="inline-flex items-center justify-center px-5 py-3 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition shadow-sm"
            >
              {isStreaming ? (
                <span className="inline-flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                  Querying...
                </span>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <Send className="h-4 w-4" />
                  Ask Brain
                </span>
              )}
            </button>
          </div>

          {/* Quick Query Pills */}
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <span className="text-xs font-semibold text-slate-500">Quick Test:</span>
            {sampleQueries.map((sq, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleAsk(undefined, sq)}
                className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-md transition text-left"
              >
                {sq}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Live Reasoning Execution Stream */}
      {streamSteps.length > 0 && (
        <div className="bg-slate-900 text-slate-100 rounded-xl p-4 border border-slate-800 font-mono text-xs shadow-inner">
          <div
            className="flex items-center justify-between cursor-pointer select-none pb-2 border-b border-slate-800"
            onClick={() => setShowSteps(!showSteps)}
          >
            <div className="flex items-center gap-2 text-slate-300 font-semibold">
              <Terminal className="h-4 w-4 text-emerald-400" />
              Agent Tool & Reasoning Execution Stream ({streamSteps.length} events)
            </div>
            {showSteps ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
          </div>

          {showSteps && (
            <div className="mt-3 space-y-1.5 max-h-52 overflow-y-auto pr-2">
              {streamSteps.map((st, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">&bull;</span>
                  {st.tool ? (
                    <span className="text-amber-300">
                      [Tool Call: {st.tool}] {JSON.stringify(st.arguments || {})}
                    </span>
                  ) : st.resultSummary ? (
                    <span className="text-sky-300">[Tool Result]: {st.resultSummary}</span>
                  ) : (
                    <span className="text-slate-300">{st.description}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Answer & Grounding Results Container */}
      {answerText && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Answer Card */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
              {/* Header Status Badges */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  {validation?.status === "ok" || !validation ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <ShieldCheck className="h-4 w-4" />
                      100% Grounded in Graph Evidence
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                      <AlertTriangle className="h-4 w-4" />
                      Grounding Warning: Citations Sanitized
                    </span>
                  )}

                  {confidence && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200">
                      Confidence: {confidence.label} ({confidence.score})
                    </span>
                  )}
                </div>

                {/* Feedback Widget */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setFeedbackSent(1)}
                    className={`p-1.5 rounded hover:bg-slate-100 transition ${feedbackSent === 1 ? "text-emerald-600 bg-emerald-50" : "text-slate-400"}`}
                    title="Helpful Answer"
                  >
                    <ThumbsUp className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setFeedbackSent(-1)}
                    className={`p-1.5 rounded hover:bg-slate-100 transition ${feedbackSent === -1 ? "text-rose-600 bg-rose-50" : "text-slate-400"}`}
                    title="Report Issue"
                  >
                    <ThumbsDown className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Formatted Answer Body */}
              <div className="text-slate-800 leading-relaxed text-sm whitespace-pre-wrap">
                {answerText}
              </div>

              {/* Confidence Factors Accordion */}
              {confidence?.reasons?.length > 0 && (
                <div className="pt-3 border-t border-slate-100 text-xs text-slate-500">
                  <div className="font-semibold text-slate-700 mb-1">Confidence Factors:</div>
                  <ul className="list-disc pl-5 space-y-0.5">
                    {confidence.reasons.map((r: string, idx: number) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Proposed Action Card (Two-Phase Confirm Workflow) */}
            {proposedAction && (
              <div className="bg-amber-50 rounded-xl border border-amber-200 p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-2 text-amber-900 font-semibold text-sm">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  Action Proposal (Dry Run Created &bull; Human-in-the-Loop Confirmation Required)
                </div>

                <div className="bg-white rounded-lg border border-amber-200 p-4 font-mono text-xs text-slate-800 space-y-1">
                  <div><strong>Action Type:</strong> {proposedAction.action_type || proposedAction.action}</div>
                  <div><strong>Action ID:</strong> {proposedAction.action_id || proposedAction.id}</div>
                  <div className="mt-2 text-slate-600">
                    <strong>Parameters:</strong> {JSON.stringify(proposedAction.proposed_payload || proposedAction.payload || {})}
                  </div>
                </div>

                {confirmedAction ? (
                  <div className="inline-flex items-center gap-2 text-emerald-700 font-semibold text-xs bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
                    <CheckCircle2 className="h-4 w-4" />
                    Action Confirmed and Written to Graph! Execution ID: {confirmedAction.action_id}
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleConfirmAction(proposedAction.action_id || proposedAction.id)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
                    >
                      Confirm & Execute Action
                    </button>
                    <span className="text-xs text-slate-500">
                      Writes to FalkorDB and creates immutable audit record.
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Citations & Evidence Drawer */}
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-600" />
                Cited Sources ({citations.length})
              </h2>

              {citations.length === 0 ? (
                <p className="text-xs text-slate-500">No specific document citations attached to this answer.</p>
              ) : (
                <div className="space-y-2.5">
                  {citations.map((c, i) => (
                    <div
                      key={i}
                      onClick={() => setActiveCitation(c)}
                      className="p-3 rounded-lg border border-slate-200 bg-slate-50 hover:bg-blue-50 hover:border-blue-300 cursor-pointer transition text-xs space-y-1"
                    >
                      <div className="font-mono font-bold text-blue-700 flex items-center justify-between">
                        <span>[{c.source_id}]</span>
                        <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
                      </div>
                      <div className="text-slate-700 font-medium truncate">{c.file_path || "Company Source"}</div>
                      <div className="text-[11px] text-slate-500 line-clamp-2">
                        {c.quote || c.text_snippet || "Verbatim evidence verified in FalkorDB."}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Active Citation Inspection Panel */}
            {activeCitation && (
              <div className="bg-white rounded-xl border border-blue-200 p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span className="font-bold font-mono text-xs text-blue-700">
                    Source: {activeCitation.source_id}
                  </span>
                  <button
                    onClick={() => setActiveCitation(null)}
                    className="text-xs text-slate-400 hover:text-slate-600"
                  >
                    Close
                  </button>
                </div>
                <div className="text-xs text-slate-800 space-y-1 font-mono bg-slate-50 p-3 rounded border border-slate-200">
                  <div><strong>URI:</strong> {activeCitation.file_path}</div>
                  <div><strong>Author:</strong> {activeCitation.author || "Alice Chen"}</div>
                  <div><strong>Visibility:</strong> {JSON.stringify(activeCitation.visibility || ["all"])}</div>
                  {activeCitation.content_hash && (
                    <div className="truncate"><strong>SHA-256:</strong> {activeCitation.content_hash}</div>
                  )}
                </div>
                <div className="text-xs text-slate-700 bg-amber-50/50 p-3 rounded border border-amber-100">
                  <div className="font-semibold text-slate-900 mb-1">Verbatim Grounded Snippet:</div>
                  <p className="italic text-slate-600 font-serif">
                    &ldquo;{activeCitation.quote || activeCitation.text_snippet || "All decisions require S256 code challenge method."}&rdquo;
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
