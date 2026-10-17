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
- [ ] **[MUST-HAVE] [Person A]**: Execute `db.py` smoke test; verify `CREATE INDEX FOR (...) ON (...)` creates range indexes cleanly.
- [ ] **[MUST-HAVE] [Person B]**: Test LiteLLM connectivity with sample prompt and tool schema.

---

### Phase 2: Ingestion & Core Agent Loop (Hours 4 – 12)
- **Person A (Data & Graph)**:
  - [ ] **[MUST-HAVE]**: Implement `ingest_structured.py` to populate `Person`, `Team`, `Project`, and `Ticket` nodes with verified Cypher queries.
  - [ ] **[MUST-HAVE]**: Implement `resolve.py` alias matching (map `@alice`, `achen` to `P_ALICE`).
  - [ ] **[MUST-HAVE]**: Implement `ingest_unstructured.py` for markdown docs and chat logs, guaranteeing that every extracted Decision is linked to an exact `Source` node with snippet text.
  - [ ] **[NICE-TO-HAVE]**: Add fuzzy name matching (RapidFuzz) in `resolve.py` for handling chat typos.
- **Person B (Tools & Agent)**:
  - [ ] **[MUST-HAVE]**: Implement the read tools in `tools.py`: `who_owns`, `who_knows_about`, and `trace_decision`.
  - [ ] **[MUST-HAVE]**: Wire `agent.py` ReAct loop with LiteLLM; enforce strict citation prompt rule: *All claims must cite [Source: ID]; if absent, state "I couldn't find this in the company graph."*
  - [ ] **[MUST-HAVE]**: Connect `get_source` tool so the agent can fetch verbatim source quotes.
  - [ ] **[NICE-TO-HAVE]**: Test tools via FastMCP server (`mcp_server.py`).

---

### Phase 3: Freshness, UI & Action Tools (Hours 12 – 20)
- **Person A (Freshness & Provenance)**:
  - [ ] **[MUST-HAVE]**: Finalize `apply_decision()` in `freshness.py` to handle the `[:SUPERSEDES]` relationship and mark old decisions `status: 'superseded'`.
  - [ ] **[MUST-HAVE]**: Test `ingest_live_decision()` with `data/live/new_billing_decision.json` to verify historical audit trail without data deletion.
  - [ ] **[NICE-TO-HAVE]**: FalkorDB GraphRAG-SDK experiment (Timeboxed to **3 hours max**; skip if complex).
- **Person B (UI & Action Tools)**:
  - [ ] **[MUST-HAVE]**: Build Streamlit chat interface in `app/streamlit_app.py` with 2-column layout (Chat left, Sources panel right).
  - [ ] **[MUST-HAVE]**: Implement action tools in `tools.py`: `create_ticket` and `draft_message` (simulated writes to graph).
  - [ ] **[MUST-HAVE]**: Embed Pyvis interactive graph component in the right pane to visually display nodes and edges.
  - [ ] **[NICE-TO-HAVE]**: Multi-tenant graph partitioning (`falkordb.select_graph(company_id)`) — strictly optional if time permits.

---

### Phase 4: Integration & Benchmark Evaluation (Hours 20 – 28)
- [ ] **[MUST-HAVE] [Person A & B]**: Run end-to-end flow from data ingestion through chat queries.
- [ ] **[MUST-HAVE] [Person B]**: Execute `tests/run_eval.py` against `tests/test_questions.json`; tune system prompt until 100% pass rate is achieved.
- [ ] **[MUST-HAVE] [Person A]**: Inspect FalkorDB queries for performance and fix any unindexed lookups.
- [ ] **[MUST-HAVE] [Person B]**: Add 1-click Demo Ribbon buttons in Streamlit to trigger Moments A, B, C, and D smoothly.

---

### 🛑 HOUR 28: FEATURE FREEZE 🛑
*No new code or architecture changes beyond this point. Focus solely on demo reliability, fallbacks, and presentation rehearsal.*

---

### Phase 5: Demo Hardening, Fallback & Rehearsal (Hours 28 – 36)
- [ ] **[MUST-HAVE] [Both]**: Rehearse 3-minute pitch according to `DEMO_PLAN.md`.
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
