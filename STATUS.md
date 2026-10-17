# OrgMind System Status & Truth Audit (Hour 14.5)

**Audit Date**: 2026-10-17 17:28 UTC  
**Auditor**: Senior Engineer & QA Lead  
**Database**: FalkorDB 4.22.1 (Redis 8.10.2 engine in Docker `localhost:6379`)  
**Active Graph**: `northwind_labs` (Clean Base State: 72 nodes, 95 edges)  
**Agent Model**: Local Ollama (`qwen2.5-coder:14b` / `llama3.1`) via LiteLLM  
**UI Server**: Streamlit 1.66.0 (Live on `http://localhost:8501`, HTTP 200)

---

## 🔍 Feature Truth Matrix

| Claimed Feature | Actual Status | Evidence & Test Output | Notes / Edge Cases |
| :--- | :---: | :--- | :--- |
| **FalkorDB Graph Storage** | **REALLY WORKS** | `scripts/smoke_test.py` PASSED.<br/>`[PASS] FalkorDB connection verified.`<br/>`72 nodes, 95 edges active.` | Range indexes operational on Node IDs. Password auto-fallback in `db.py` works. |
| **Safe Demo Reset** | **REALLY WORKS** | `scripts/reset_demo.py` PASSED.<br/>`[PASS] Successfully wiped 'northwind_labs'.`<br/>`[DONE] Clean base state: 72 nodes, 95 edges.` | Deletes ONLY `northwind_labs` via `GRAPH.DELETE`. Leaves `/data/live/` untouched. |
| **Structured Ingestion** | **REALLY WORKS** | `python orgmind/ingest_structured.py`<br/>`[Ingest] Loaded 11 Person, 4 Team, 4 Project, 3 Ticket nodes.` | CSVs & JSON tickets loaded cleanly. |
| **Unstructured Ingestion** | **REALLY WORKS** | `python orgmind/ingest_unstructured.py`<br/>`Processed docs/auth_architecture.md`<br/>`Processed docs/billing_migration.md`<br/>`Processed 3 chat jsonl files.` | Parses Markdown ADRs and JSONL chats. Links `Source` chunks and topics. |
| **Entity Resolution** | **REALLY WORKS** | `resolve_person('Pri') -> 'P_PRIYA'`<br/>`resolve_person('Ro') -> 'P_ROHAN'`<br/>`resolve_person('@alice') -> 'P_ALICE'` | Exact alias matching. Fuzzy typo matching is slated for Phase 2. |
| **Tool: who_owns** | **REALLY WORKS** | `who_owns('OAuth Upgrade') -> {'target_name': 'OAuth 2.1 & Keycloak Migration', 'owner_name': 'Platform & Auth', 'lead_name': 'Alice Chen', 'found': True}` | Enhanced with token splitting and project ID matching. |
| **Tool: who_knows_about** | **REALLY WORKS** | `who_knows_about('Paynova') -> Top: Rohan Iyer (4 items), Aarav Mehta (4 items)` | Counts authored items and chat mentions. Weighted scoring is slated for Phase 4. |
| **Tool: trace_decision** | **REALLY WORKS** | `trace_decision('OAuth') -> Decision DEC_AUTH_2026_01, Source SRC_DOC_AUTH_01` | Multi-hop OPTIONAL MATCH verified in FalkorDB. |
| **Freshness & Superseding** | **PARTIAL** | `freshness.apply_decision()` works in Python, but live update UI workflow is not yet interactive preview/commit. | Logic exists; UI integration & idempotency hardening needed in Phase 2. |
| **Citation Enforcement** | **PARTIAL** | Agent prompt commands citation `[Source: ID]`; confirmed in sample runs (`AGENT RESPONSE: ... [Source: SRC_DOC_AUTH_01]`). | Currently prompt-only. Hard programmatic validator needed in Phase 3. |
| **Simulated Actions** | **PARTIAL** | `create_ticket` & `draft_message` write simulated nodes to graph. | Propose-then-confirm UI flow needed in Phase 4/5. |
| **Streamlit User Interface** | **REALLY WORKS** | `curl -I http://localhost:8501/` returned `HTTP/1.1 200 OK`. Interactive Pyvis graph renders in-memory HTML. | Tested in browser. UI explainability panel needed in Phase 5. |
| **MCP Server** | **UNTESTED** | FastMCP stub exists in `orgmind/mcp_server.py`. | Dedicated test client & proof needed in Phase 6. |

---

## ⚙️ Assumptions Log (Rule: No Questions Unless Blocked)

1. **Local Model Availability**: Ollama is installed and running with `qwen2.5-coder:14b`. We assume local inference is preferred for offline demo reliability, but will support hosted models via standard LiteLLM environment variables.
2. **Graph Naming**: Default graph name is `northwind_labs`. Reset scripts wipe ONLY `northwind_labs`. Any secondary tenant graph will be strictly namespaced (e.g. `northwind_labs_b`).
3. **FalkorDB Authentication**: Local Docker container operates without password. `db.py` gracefully handles passwordless Redis even if passwords exist in `.env`.
4. **Data Seed Scope**: Phase 1 will expand base dataset to 10-12 documents, 12-15 tickets, 60-80 messages, and 8-12 decisions without altering existing entity IDs.

---

## 🛠️ Verification Command Output (Phase 0 Acceptance)

```text
PS C:\Users\sauja\Downloads\New folder> python scripts/smoke_test.py
==================================================
 [OrgMind Smoke Test] Starting System Verification 
==================================================
[PASS] FalkorDB connection verified.
[INFO] Current graph status: 72 nodes, 95 edges.
[PASS] Node & edge presence confirmed.

--- Verifying 5 Core Cypher Queries ---
[PASS] Query 1: Who Owns executed (3 sample records returned).
[PASS] Query 2: Who Knows About executed (3 sample records returned).
[PASS] Query 3: Decision Trace executed (2 sample records returned).
[PASS] Query 4: Supersedes Linkage executed (2 sample records returned).
[PASS] Query 5: What Changed executed (2 sample records returned).

--- Verifying Agent Tools Execution ---
[PASS] Tool who_owns('OAuth') verified -> Platform & Auth
[PASS] Tool who_knows_about('Paynova') verified -> Top expert: Rohan Iyer
[PASS] Tool trace_decision('OAuth') verified -> Decision: DEC_AUTH_2026_01

==================================================
 [OrgMind Smoke Test] ALL CHECKS PASSED (EXIT 0)   
==================================================
```
