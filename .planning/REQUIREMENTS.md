# Requirements: OrgMind UI & Company Brain

**Defined:** 2026-10-17  
**Core Value:** Unified FalkorDB knowledge graph queried by an autonomous agent with verifiable provenance and live freshness.

## v1 Requirements: UI & Presentation Excellence

### HUD & Diagnostics
- [x] **HUD-01**: Display real-time FalkorDB status banner (Online/Offline, host, port).
- [x] **HUD-02**: Display live graph scale dynamically queried from FalkorDB (`163 Nodes • 267 Edges`).
- [x] **HUD-03**: Display Grounding Guard badge (`Zero-Hallucination Active`).
- [x] **HUD-04**: Display active reasoning engine model name.

### Demo Control Ribbon
- [x] **RIB-01**: Provide 1-click execution for Moment A (Ownership & Weighted Expertise).
- [x] **RIB-02**: Provide 1-click execution for Moment B (Decision Lineage & Source Provenance).
- [x] **RIB-03**: Provide 1-click execution for Moment C (Live Superseding Pipeline).
- [x] **RIB-04**: Provide 1-click execution for Moment D (Dissenting Draft vs Ratified Policy).
- [x] **RIB-05**: Provide 1-click execution for Moment E (Multi-Hop Impact & Blockers).
- [x] **RIB-06**: Provide 1-click execution for Clean Baseline Reset (restoring 163 nodes in under 2 seconds).

### Interactive Chat & Explainability
- [x] **CHAT-01**: Render user and assistant chat bubbles with distinct avatars (`🧑‍💻` and `🧠`).
- [x] **CHAT-02**: Provide expandable Reasoning & Tool Execution trace per turn with latency and tool call arguments.
- [x] **CHAT-03**: Render Human-in-the-Loop Action Confirmation card for pending graph mutations.
- [x] **CHAT-04**: Provide quick suggested prompt chips for rapid exploration.

### Knowledge Graph Visualizer & Inspector
- [x] **VIS-01**: Embed interactive Pyvis force-directed graph with active path highlighting in gold.
- [x] **VIS-02**: Support visual subgraph filtering dropdown (Overview, Decisions & Provenance, People & Ownership, Tickets & Blockers).
- [x] **VIS-03**: Render color-coded legend pills matching node categories.
- [x] **VIS-04**: Tabbed right inspector panel for Sources, Graph Explorer, Live Pipeline, and Multi-Hop Impact.

### Live Pipeline & Multi-Hop Traversal
- [x] **PIPE-01**: Support 2-step live ingestion (Preview Mutation -> Commit with Idempotency).
- [x] **PIPE-02**: Multi-hop dependency traversal identifying impacted tickets, responsible personnel, and critical blocker callouts (`TICK-202` blocked by `TICK-201`).

---
*Requirements defined and verified: 2026-10-17*
