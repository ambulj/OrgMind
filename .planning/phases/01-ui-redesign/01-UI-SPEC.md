# UI-SPEC: OrgMind Frontend Design Contract

**Phase:** Phase 01 — UI Redesign & Streamlit Explainability  
**Target:** `app/streamlit_app.py`  
**Status:** Approved & Implemented ✓  

---

## 1. Visual Design Tokens

### Color Palette (Dark Theme / Glassmorphism)
- **Base Background**: `#0d1117` (GitHub Dark Dimmed tone)
- **Surface Card**: `#161b22` (Subtle elevated container)
- **Border**: `#30363d` (High-definition contrast separator)
- **Accent Primary**: `#58a6ff` (Electric blue for links and active states)
- **Text Primary**: `#e6edf3` (High legibility body text)
- **Text Muted**: `#8b949e` (Secondary labels and captions)

### Entity Badge Taxonomy
| Entity Type | Background | Text Color | Meaning |
| :--- | :--- | :--- | :--- |
| **Person** | `#238636` (Green) | `#ffffff` | Employee / Individual Contributor / Lead |
| **Team** | `#1f6feb` (Blue) | `#ffffff` | Department / Engineering Squad |
| **Project** | `#8957e5` (Purple) | `#ffffff` | Corporate Initiative / Repository |
| **Decision** | `#d29922` (Amber) | `#ffffff` | Architectural Decision Record / Policy |
| **Source** | `#388bfd` (Cyan) | `#ffffff` | Verbatim Evidence Chunk in FalkorDB |
| **Ticket** | `#da3633` (Red) | `#ffffff` | Issue / Task / Incident |
| **Active Highlight** | `#FFD700` (Gold) | `#000000` | Node actively traversed in recent turn |

---

## 2. Layout Hierarchy & Component Architecture

### A. Header & Live HUD Banner
- **Header Card**: Gradient `linear-gradient(135deg, #161b22 0%, #0d1117 100%)` with title and track subtitle.
- **HUD Metric Cards (4-column grid)**:
  1. `FalkorDB`: Status indicator (`🟢 Online`)
  2. `Graph Scale`: Dynamically queried live count (`📊 163 Nodes • 267 Edges`)
  3. `Grounding Guard`: Zero-hallucination verification status (`🛡️ Active`)
  4. `Reasoning Engine`: Active model display (`🤖 qwen2.5-coder:14b`)

### B. 1-Click Demo Control Ribbon
Six high-contrast action cards styled with emojis and subtitles:
- **Moment A**: `📌 Moment A: Ownership & Expertise`
- **Moment B**: `📜 Moment B: Decision Provenance`
- **Moment C**: `⚡ Moment C: Live Superseding`
- **Moment D**: `⚖️ Moment D: Draft vs Decision`
- **Moment E**: `🎯 Moment E: Impact & Blockers`
- **Reset**: `🔄 Reset Baseline (Restore 163 Nodes)`

### C. Left Column: Chat & Explainability (58% Width)
- **Chat History**:
  - User messages with `🧑‍💻` avatar.
  - Assistant responses with `🧠` avatar.
- **Explainability Trace (`st.expander`)**:
  - Displays execution latency in seconds.
  - Formatted Python code snippets for each tool called with exact parameters.
  - Verified source IDs list.
  - Status badge: `🛡️ Zero-Hallucination Verified` vs `⚠️ Unverified`.
- **Human-in-the-Loop Action Confirmation**:
  - Card rendered when a write action is proposed (`create_ticket`, `draft_message`, `assign_task`).
  - Two buttons: `✅ Confirm & Write to Graph` and `❌ Cancel Proposal`.
- **Quick Suggested Prompts**:
  - Chips for rapid demo execution (`"Who owns Customer Portal?"`, `"What is our DB security policy?"`, `"Who knows Paynova?"`).

### D. Right Column: 4-Tab Inspector (42% Width)
- **Tab 1 (📑 Verified Sources)**:
  - Source ID pill and file path origin.
  - Left-accented quotation box (`border-left: 3px solid #58a6ff`) containing verbatim text chunks.
- **Tab 2 (🕸️ Knowledge Graph)**:
  - Subgraph filter dropdown:
    - `All Nodes (Overview)`
    - `Decisions & Provenance`
    - `People & Ownership`
    - `Tickets & Blockers`
  - Color-coded legend pills at top.
  - Pyvis force-directed graph with physics (`gravity: -60`, `spring_length: 110`).
  - Active nodes highlighted in `#FFD700` Gold with enlarged size (`28px` vs `18px`).
- **Tab 3 (⚡ Live Ingestion Pipeline)**:
  - Live payload selector dropdown (`live_decision_reversal.json` vs `new_billing_decision.json`).
  - Two-step execution: `1. Generate Extraction Preview` -> `2. Commit Decision to Graph`.
  - Preview card displays target decision, supersedes candidate, ratified text, and origin file.
  - Idempotency feedback alert if re-committed without modification.
- **Tab 4 (🎯 Multi-hop Impact Viewer)**:
  - Input field for target topic/decision (default: `Paynova`).
  - Summary sentence generated from traversal.
  - Two-column impact grid:
    - Column 1: Impacted Tickets with status badges.
    - Column 2: Critical Blocker callouts (`⚠️ TICK-202 is BLOCKED BY TICK-201`).
  - Responsible team members and reason list.
  - Expandable provenance path strings.

### E. Sidebar Diagnostics
- `🚀 Run Preflight Health Check`: Invokes automated 6-point verification suite with direct UI status output.
- Direct links to FalkorDB Browser (`http://localhost:3000`) and official documentation.
- `🧹 Clear Chat Transcript` button.

---

## 3. Copywriting & Interaction Contracts

### Zero-Hallucination Response Contract
When a query references an entity not in FalkorDB, the agent MUST return:
> *"I couldn't find this in the company graph. No active project, owner, or documents exist for this query in Northwind Labs."*

### Provenance Citation Contract
Every factual statement derived from the graph MUST include its source ID:
> *"Northwind Labs officially enforces OAuth 2.1 with PKCE [Source: SRC_DOC_AUTH_01]..."*

### Simulated Action Audit Contract
When simulated write tools execute, the agent MUST explicitly state the simulated ID:
> *"Ticket created with simulated ID: TICK-SIM-7090. Action recorded in FalkorDB graph."*

---

## 4. Verification Checklist

- [x] Streamlit server starts headless without errors on port 8501.
- [x] Preflight automated test reports 6/6 PASS.
- [x] Pyvis component renders cleanly inside 480px height container without clipping.
- [x] All 5 Demo Moments execute with 1 click and update reasoning traces and source tabs.
- [x] Reset Baseline wipes live state and restores exact 163 nodes in under 2 seconds.
