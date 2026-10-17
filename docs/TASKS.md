# OrgMind 36-Hour Hackathon Execution Plan

> **Hackathon Timeline**: 36 Hours total.  
> **Feature Freeze**: Hour 28 (No new features after Hour 28; polish, test, and rehearse only).  
> **Team**: 2 Engineers (Person A & Person B).

---

## 👥 Role Division & Responsibility Matrix

| Role | Engineer | Focus Areas | Primary Files |
| :--- | :--- | :--- | :--- |
| **Backend & Graph Architect** | **Person A** | FalkorDB schema, CSV & JSON ingestion, LLM doc extraction, Entity Resolution, Freshness / Superseding pipeline. | `orgmind/db.py`<br/>`orgmind/ingest_structured.py`<br/>`orgmind/ingest_unstructured.py`<br/>`orgmind/resolve.py`<br/>`orgmind/freshness.py`<br/>`data/*` |
| **Agent & Full-Stack Architect** | **Person B** | Tool definitions, ReAct tool-calling loop (LiteLLM), Citation enforcement, Streamlit UI, Pyvis graph visualization, Demo automation. | `orgmind/tools.py`<br/>`orgmind/agent.py`<br/>`orgmind/mcp_server.py`<br/>`app/streamlit_app.py`<br/>`tests/*`<br/>`DEMO_PLAN.md` |

---

## ⏱️ 36-Hour Roadmap & Milestones

### Phase 1: Setup & Foundational Bootstrap (Hours 0 – 4)
- [x] **[MUST-HAVE] [Both]**: Launch FalkorDB via Docker container; verify port 6379 connectivity.
- [x] **[MUST-HAVE] [Both]**: Create repository skeleton, placeholder files, `.env.example`, `requirements.txt`.
- [x] **[MUST-HAVE] [Person A]**: Execute `db.py` smoke test; verify `CREATE INDEX FOR (...) ON (...)` creates range indexes cleanly.
- [x] **[MUST-HAVE] [Person B]**: Test LiteLLM connectivity with sample prompt and tool schema.

---

### Phase 2: Ingestion & Core Agent Loop (Hours 4 – 12)
- **Person A (Data & Graph)**:
  - [x] **[MUST-HAVE]**: Implement `ingest_structured.py` to populate `Person`, `Team`, `Project`, and `Ticket` nodes with verified Cypher queries.
  - [x] **[MUST-HAVE]**: Implement `resolve.py` alias matching (map `@alice`, `achen` to `P_ALICE`).
  - [x] **[MUST-HAVE]**: Implement `ingest_unstructured.py` for markdown docs and chat logs, guaranteeing that every extracted Decision is linked to an exact `Source` node with snippet text.
  - [x] **[NICE-TO-HAVE]**: Add fuzzy name matching (`difflib`) in `resolve.py` for handling chat typos and unknown handle flagging.
- **Person B (Tools & Agent)**:
  - [x] **[MUST-HAVE]**: Implement the read tools in `tools.py`: `who_owns`, `who_knows_about`, and `trace_decision`.
  - [x] **[MUST-HAVE]**: Wire `agent.py` ReAct loop with LiteLLM; enforce strict citation prompt rule: *All claims must cite [Source: ID]; if absent, state "I couldn't find this in the company graph."*
  - [x] **[MUST-HAVE]**: Connect `get_source` tool so the agent can fetch verbatim source quotes.
  - [x] **[NICE-TO-HAVE]**: Test tools via FastMCP server (`mcp_server.py`).

---

### Phase 3: Freshness, UI & Action Tools (Hours 12 – 20)
- **Person A (Freshness & Provenance)**:
  - [x] **[MUST-HAVE]**: Finalize `commit_decision()` in `freshness.py` to handle the `[:SUPERSEDES]` relationship and mark old decisions `status: 'superseded'`.
  - [x] **[MUST-HAVE]**: Test `commit_decision()` with `data/live/live_decision_reversal.json` to verify historical audit trail without data deletion and enforce idempotency.
  - [x] **[NICE-TO-HAVE]**: Multi-hop graph dependency analysis `impact_analysis()` traversing Decision -> Topic -> Projects -> Tickets -> Blockers -> People.
- **Person B (UI & Action Tools)**:
  - [x] **[MUST-HAVE]**: Build Streamlit chat interface in `app/streamlit_app.py` with 2-column layout (Chat left, 4-Tab Inspector right).
  - [x] **[MUST-HAVE]**: Implement action tools in `tools.py`: `create_ticket`, `draft_message`, and `assign_task` with Human-in-the-Loop simulation confirmation (`confirm=False`).
  - [x] **[MUST-HAVE]**: Embed Pyvis interactive graph component in the right pane to visually display nodes and edges with active node highlighting.
  - [x] **[NICE-TO-HAVE]**: FastMCP client test suite (`scripts/test_mcp_client.py`) testing tool discovery and invocation over MCP protocol.

---

### Phase 4: Integration & Benchmark Evaluation (Hours 20 – 28)
- [x] **[MUST-HAVE] [Person A & B]**: Run end-to-end flow from data ingestion through chat queries.
- [x] **[MUST-HAVE] [Person B]**: Execute `tests/run_eval.py` against `tests/test_questions.json` (14-question benchmark suite).
- [x] **[MUST-HAVE] [Person A]**: Inspect FalkorDB queries for performance, verify range indexes, and optimize query latency.
- [x] **[MUST-HAVE] [Person B]**: Add 1-click Demo Ribbon buttons in Streamlit to trigger Moments A, B, C, D, and E + 1-Click Clean Reset.

---

### 🛑 HOUR 28: FEATURE FREEZE (COMPLETED AHEAD OF SCHEDULE AT HOUR 22) 🛑
*No new code or architecture changes beyond this point. Focus solely on demo reliability, fallbacks, and presentation rehearsal.*

---

### Phase 5: Demo Hardening, Fallback & Rehearsal (Hours 28 – 36)
- [x] **[MUST-HAVE] [Both]**: Rehearse 3-minute pitch according to `DEMO_PLAN.md`.
- [x] **[MUST-HAVE] [Both]**: Preflight automated verification suite (`scripts/preflight.py`) testing 6/6 critical subsystems.
- [ ] **[MUST-HAVE] [Person B]**: Record a 3-minute screen capture video of the complete live demo as an emergency fallback if Docker/network fails during presentation.
- [ ] **[MUST-HAVE] [Person A]**: Prepare 2-3 slide deck summarizing the FalkorDB architecture and Track 3 value proposition.
- [ ] **[MUST-HAVE] [Both]**: Final cleanup of repository and submission links.

---

## 🎯 MUST-HAVE vs NICE-TO-HAVE Summary

| Category | Must-Have (Hackathon Deliverable) | Nice-To-Have (Post-Freeze / Bonus) |
| :--- | :--- | :--- |
| **Data & Graph** | Synthetic Northwind Labs dataset (60 items), FalkorDB range indexes, `Source` provenance nodes. | Vector embeddings for similarity search; automatic PDF parser. |
| **Freshness** | `SUPERSEDES` relationship and `status: 'superseded'` updates on old decisions. | Full automated git-style branching of graph states. |
| **Agent** | ReAct tool loop (LiteLLM), zero-hallucination citation guard, ownership, who-knows ranking. | Autonomous multi-agent debates; memory persistence across browser restarts. |
| **Actions** | Simulated `create_ticket` and `draft_message` written back to graph. | Live Slack bot webhook; live Jira API integration. |
| **Multi-Tenancy** | Single company graph (`northwind_labs`). | Dynamic multi-tenant company switcher (`select_graph(org_id)`). |
