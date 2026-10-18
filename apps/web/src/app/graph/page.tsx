"use client";

import React, { useState, useEffect, useRef } from "react";
import { getAuthHeaders, defaultUserContext } from "@/lib/api";
import { Network, Search, Layers, Compass, Info, X, ArrowRight, RefreshCw, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  properties: Record<string, any>;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
  properties: Record<string, any>;
}

export default function GraphExplorerPage() {
  const [mode, setMode] = useState<"neighborhood" | "path">("neighborhood");
  const [centerEntity, setCenterEntity] = useState<string>("P_ALICE");
  const [hops, setHops] = useState<number>(2);
  const [asOfDate, setAsOfDate] = useState<string>("");
  const [fromEntity, setFromEntity] = useState<string>("P_ALICE");
  const [toEntity, setToEntity] = useState<string>("OAuth");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphStats, setGraphStats] = useState<{ nodes: number; edges: number }>({ nodes: 0, edges: 0 });

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<any>(null);

  // Initialize and update Cytoscape
  const renderGraph = async (nodes: GraphNode[], edges: GraphEdge[]) => {
    if (!containerRef.current) return;

    // Dynamically import cytoscape to avoid SSR issues
    const cytoscape = (await import("cytoscape")).default;

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const elements = [
      ...nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.name || n.id,
          type: n.type || "Entity",
          props: n.properties,
        },
      })),
      ...edges.map((e, idx) => ({
        data: {
          id: `e_${e.source}_${e.target}_${idx}`,
          source: e.source,
          target: e.target,
          label: e.type || "RELATED",
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele: any) => {
              const t = ele.data("type");
              switch (t) {
                case "Person": return "#3b82f6"; // blue
                case "Project": return "#8b5cf6"; // purple
                case "Team": return "#10b981"; // emerald
                case "Decision": return "#f59e0b"; // amber
                case "Ticket": return "#ef4444"; // red
                case "Document": return "#64748b"; // slate
                case "Topic": return "#06b6d4"; // cyan
                default: return "#6b7280";
              }
            },
            label: "data(label)",
            color: "#1e293b",
            "font-size": "12px",
            "font-weight": "bold",
            "text-valign": "bottom",
            "text-margin-y": 6,
            width: 38,
            height: 38,
            "border-width": 2,
            "border-color": "#ffffff",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#cbd5e1",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": "9px",
            color: "#64748b",
            "text-rotation": "autorotate",
            "text-margin-y": -6,
          },
        },
        {
          selector: ":selected",
          style: {
            "border-width": 4,
            "border-color": "#2563eb",
            "line-color": "#2563eb",
            "target-arrow-color": "#2563eb",
          },
        },
      ],
      layout: {
        name: "cose",
        padding: 40,
        animate: true,
        animationDuration: 500,
        nodeOverlap: 20,
        idealEdgeLength: 100,
      },
    });

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      setSelectedNode({
        id: node.data("id"),
        name: node.data("label"),
        type: node.data("type"),
        properties: node.data("props") || {},
      });
    });

    cyRef.current = cy;
    setGraphStats({ nodes: nodes.length, edges: edges.length });
  };

  const loadNeighborhood = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        entity: centerEntity.trim(),
        hops: hops.toString(),
      });
      if (asOfDate) {
        params.set("as_of", asOfDate);
      }

      const res = await fetch(`/api/v1/graph/neighborhood?${params.toString()}`, {
        headers: getAuthHeaders(defaultUserContext),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err?.error?.message || `HTTP ${res.status}`);
      }

      const data = await res.json();
      await renderGraph(data.nodes || [], data.edges || []);
    } catch (e: any) {
      setError(e.message || "Failed to load graph neighborhood");
    } finally {
      setLoading(false);
    }
  };

  const loadShortestPath = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        from: fromEntity.trim(),
        to: toEntity.trim(),
      });

      const res = await fetch(`/api/v1/graph/path?${params.toString()}`, {
        headers: getAuthHeaders(defaultUserContext),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err?.error?.message || `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (!data.found) {
        setError(`No path discovered between "${fromEntity}" and "${toEntity}".`);
        if (cyRef.current) cyRef.current.destroy();
        setGraphStats({ nodes: 0, edges: 0 });
        return;
      }

      // Reconstruct edges between sequential nodes if not fully linked
      const edges: GraphEdge[] = [];
      const nodes: GraphNode[] = data.nodes || [];
      for (let i = 0; i < nodes.length - 1; i++) {
        const relType = data.edges?.[i]?.type || "CONNECTS_TO";
        edges.push({
          source: nodes[i].id,
          target: nodes[i + 1].id,
          type: relType,
          properties: data.edges?.[i]?.properties || {},
        });
      }

      await renderGraph(nodes, edges);
    } catch (e: any) {
      setError(e.message || "Failed to find semantic path");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNeighborhood();
  }, []);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.2);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit();

  return (
    <div className="space-y-6">
      {/* Page Title & Controls Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Network className="h-5 w-5 text-blue-600" />
            Interactive Knowledge Graph Explorer
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Explore entity neighborhoods or compute shortest semantic paths across the FalkorDB company graph.
          </p>
        </div>

        {/* Tab Buttons for Mode */}
        <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
          <button
            onClick={() => setMode("neighborhood")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
              mode === "neighborhood" ? "bg-white text-blue-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Neighborhood Exploration
          </button>
          <button
            onClick={() => setMode("path")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
              mode === "path" ? "bg-white text-blue-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Semantic Shortest Path
          </button>
        </div>
      </div>

      {/* Control Panel Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        {mode === "neighborhood" ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              loadNeighborhood();
            }}
            className="flex flex-wrap items-center gap-4"
          >
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-600 mb-1">Center Entity / ID</label>
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  value={centerEntity}
                  onChange={(e) => setCenterEntity(e.target.value)}
                  placeholder="e.g. P_ALICE, OAuth, Project Phoenix"
                  className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
            </div>

            <div className="w-28">
              <label className="block text-xs font-semibold text-slate-600 mb-1">Radius (Hops)</label>
              <select
                value={hops}
                onChange={(e) => setHops(Number(e.target.value))}
                className="w-full py-1.5 px-3 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={1}>1 Hop</option>
                <option value={2}>2 Hops</option>
                <option value={3}>3 Hops</option>
              </select>
            </div>

            <div className="w-48">
              <label className="block text-xs font-semibold text-slate-600 mb-1">As-Of Timestamp (Optional)</label>
              <input
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                className="w-full py-1.5 px-3 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="pt-5">
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-sm flex items-center gap-1.5 transition disabled:opacity-50"
              >
                {loading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                Explore
              </button>
            </div>
          </form>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              loadShortestPath();
            }}
            className="flex flex-wrap items-center gap-4"
          >
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-600 mb-1">Starting Entity</label>
              <input
                type="text"
                value={fromEntity}
                onChange={(e) => setFromEntity(e.target.value)}
                placeholder="e.g. P_ALICE"
                className="w-full px-3 py-1.5 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div className="flex items-center justify-center pt-5 text-slate-400">
              <ArrowRight className="h-5 w-5" />
            </div>

            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-slate-600 mb-1">Target Entity</label>
              <input
                type="text"
                value={toEntity}
                onChange={(e) => setToEntity(e.target.value)}
                placeholder="e.g. OAuth or P_BOB"
                className="w-full px-3 py-1.5 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div className="pt-5">
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-sm flex items-center gap-1.5 transition disabled:opacity-50"
              >
                {loading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Compass className="h-3.5 w-3.5" />}
                Find Path
              </button>
            </div>
          </form>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Main Canvas + Inspector Area */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Cytoscape Container */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 shadow-sm relative overflow-hidden flex flex-col h-[650px]">
          {/* Top Canvas Toolbar */}
          <div className="absolute top-4 left-4 z-10 flex items-center gap-2 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-slate-200 shadow-sm text-xs font-medium text-slate-700">
            <span>{graphStats.nodes} nodes</span>
            <span>&bull;</span>
            <span>{graphStats.edges} edges</span>
          </div>

          <div className="absolute top-4 right-4 z-10 flex items-center gap-1 bg-white/90 backdrop-blur-sm p-1 rounded-lg border border-slate-200 shadow-sm">
            <button
              onClick={handleZoomIn}
              title="Zoom In"
              className="p-1.5 hover:bg-slate-100 rounded text-slate-600"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              onClick={handleZoomOut}
              title="Zoom Out"
              className="p-1.5 hover:bg-slate-100 rounded text-slate-600"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <button
              onClick={handleFit}
              title="Fit to Screen"
              className="p-1.5 hover:bg-slate-100 rounded text-slate-600"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>

          {/* Cytoscape DOM Mounting Point */}
          <div ref={containerRef} className="w-full h-full bg-slate-50/50" />
        </div>

        {/* Node Properties & Evidence Inspector Drawer */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col h-[650px] overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Info className="h-4 w-4 text-blue-600" />
              Entity Inspector
            </h3>
            {selectedNode && (
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {selectedNode ? (
            <div className="space-y-4 text-sm">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Type</span>
                <div className="mt-0.5">
                  <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                    {selectedNode.type}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Identifier</span>
                <div className="mt-0.5 font-mono text-xs text-slate-800 break-all bg-slate-50 p-1.5 rounded border border-slate-200">
                  {selectedNode.id}
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Display Label</span>
                <div className="mt-0.5 font-semibold text-slate-900">{selectedNode.name}</div>
              </div>

              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Properties</span>
                <div className="mt-1 space-y-2 max-h-72 overflow-y-auto">
                  {Object.entries(selectedNode.properties).map(([k, v]) => (
                    <div key={k} className="bg-slate-50 p-2 rounded border border-slate-200 text-xs">
                      <div className="font-semibold text-slate-700">{k}:</div>
                      <div className="text-slate-600 mt-0.5 break-words font-mono text-[11px]">
                        {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={() => {
                    setCenterEntity(selectedNode.id);
                    setMode("neighborhood");
                    loadNeighborhood();
                  }}
                  className="w-full py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-lg text-xs font-semibold transition"
                >
                  Center Neighborhood Here
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 p-4">
              <Network className="h-10 w-10 text-slate-300 mb-2" />
              <p className="text-xs">Click on any node in the graph canvas to inspect its metadata, properties, and relationships.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
