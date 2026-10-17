# 🧠 OrgMind: Company Brain & Knowledge Graph

[![Track](https://img.shields.io/badge/Hackathon-Track%203%3A%20Company%20Brain-blue.svg)](#)
[![Graph Database](https://img.shields.io/badge/Database-FalkorDB-red.svg)](https://docs.falkordb.com)
[![LLM Router](https://img.shields.io/badge/LLM-LiteLLM-green.svg)](https://github.com/BerriAI/litellm)
[![UI](https://img.shields.io/badge/UI-Streamlit%20%2B%20Pyvis-orange.svg)](#)

> **OrgMind** connects people, teams, projects, documents, and decisions into a single high-performance knowledge graph powered by **FalkorDB**. An autonomous agent answers questions, traces decisions with exact citations, tracks superseding changes in real time, and executes simulated company actions.

---

## 🌟 Key Capabilities

1. **Unified Graph**: Connects structured data (people, teams, projects) and unstructured knowledge (architecture specs, Jira tickets, Slack chats) into one graph.
2. **Who Owns & Who Knows**: Identifies project leads and ranks people by factual evidence of knowledge across documents and chats.
3. **Decision Lineage & Provenance**: Every decision is linked to an immutable `Source` node with exact text chunks and file origins.
4. **Non-Destructive Freshness**: When a new decision is made, the old decision is never deleted; it is marked `superseded` and linked via `[:SUPERSEDES]` to preserve the historical audit trail.
5. **Strict Grounding & Zero Hallucination**: The agent answers exclusively from retrieved graph facts with citations. If no evidence exists, it states: *"I couldn't find this in the company graph."*
6. **Simulated Workflows**: Drafts messages and creates tickets directly into the graph.

---

## 📁 Repository Structure

```text
├── ARCHITECTURE.md          # System architecture, glossary, Mermaid diagram
├── SCHEMA.md                # Node/edge definitions, indexes, 5 verified Cypher queries
├── SETUP.md                 # Step-by-step setup guide for Windows, Mac & Linux
├── TASKS.md                 # 36-hour sprint plan divided between Person A and Person B
├── DEMO_PLAN.md             # 3-minute hackathon presentation script with 4 demo moments
├── docker-compose.yml       # Local FalkorDB container & optional MCP server
├── requirements.txt         # Python dependencies
├── .env.example             # Environment configuration template
│
├── data/                    # Synthetic company dataset (Northwind Labs)
│   ├── people.csv           # Master employee records & handles
│   ├── teams.csv            # Teams & department leads
│   ├── projects.csv         # Active initiatives
│   ├── tickets.json         # Issue tracker data
│   ├── docs/                # Architecture decision records (.md)
│   ├── chats/               # Team communications (.jsonl)
│   └── live/                # Live decision update payload for demo
│
├── orgmind/                 # Core Python backend package
│   ├── db.py                # FalkorDB connection, index creation & smoke test
│   ├── ingest_structured.py # Loads CSVs and tickets into FalkorDB
│   ├── ingest_unstructured.py # LLM extraction -> validated schema -> Source nodes
│   ├── resolve.py           # Entity resolution (handles & aliases to canonical IDs)
│   ├── freshness.py         # Decision superseding & non-destructive freshness logic
│   ├── tools.py             # Agent tools (who_owns, trace_decision, create_ticket, etc.)
│   ├── mcp_server.py        # Custom FastMCP server exposing tools to external clients
│   └── agent.py             # Provider-agnostic LiteLLM tool-calling agent with citation guard
│
├── app/
│   └── streamlit_app.py     # 2-column UI (Chat + Source Inspector + Pyvis Network)
│
└── tests/
    ├── test_questions.json  # Benchmark evaluation questions with expected outcomes
    └── run_eval.py          # Automated evaluation scoring harness
```

---

## 🚀 Quick Start (3 Steps)

### 1. Launch FalkorDB via Docker
```bash
docker run -p 6379:6379 -p 3000:3000 --name falkordb -d falkordb/falkordb:latest
```

### 2. Install Dependencies & Configure
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your LLM API Key (OpenAI, Anthropic, or Gemini)
```

### 3. Bootstrap & Launch
```bash
# 1. Verify connection & indexes
python orgmind/db.py

# 2. Ingest structured and unstructured data into FalkorDB
python orgmind/ingest_structured.py
python orgmind/ingest_unstructured.py

# 3. Run Preflight Health Check (verifies DB, graph baseline, MCP, assets)
python scripts/preflight.py

# 4. Launch Streamlit UI
streamlit run app/streamlit_app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🔌 Model Context Protocol (MCP) Server

OrgMind exposes its entire company brain capabilities over the open **Model Context Protocol** (FastMCP / MCPServer):
```bash
# Run standalone MCP server over stdio (compatible with Claude Desktop, Cursor, AGY):
python orgmind/mcp_server.py

# Run MCP verification suite:
python scripts/test_mcp_client.py
```

Exposed MCP Tools:
- `who_owns`: Finds project leads and team ownership.
- `who_knows_about`: Ranks members by weighted evidence score (specs = 3.0, tickets = 2.0, chats = 1.0).
- `trace_decision`: Traces active and historical superseded decisions with source file links.
- `compare_draft_vs_decision`: Compares dissenting preliminary drafts against ratified policies.
- `impact_analysis`: Multi-hop graph traversal surfacing affected tickets, projects, and blockers.
- `create_ticket`, `draft_message`, `assign_task`: Human-in-the-loop action proposals (`confirm=False`).

---

## 🧪 Benchmark Evaluation Harness

Validate the agent against the complete benchmark test set:
```bash
# Run benchmark on all questions:
python tests/run_eval.py --limit 6

# Specify model or custom report:
python tests/run_eval.py --model ollama/qwen2.5-coder:14b --output tests/benchmark_report.json
```

---

## 🏆 Hackathon Track 3 Judging Criteria Alignment

| Track 3 Judging Requirement | OrgMind Implementation | Verification Command |
| :--- | :--- | :--- |
| **1. All in ONE Graph** | FalkorDB models People, Teams, Projects, Docs, Tickets, Decisions, and Chats in `northwind_labs`. | `python orgmind/db.py` |
| **2. Who Owns & Who Knows** | Range-indexed ownership queries + weighted evidence ranking breaking near-ties. | `python scripts/test_tools_phase4.py` |
| **3. Tracing Decisions** | Verbatim provenance chunks linked via `Source` nodes; zero hallucinations. | `python tests/run_eval.py --limit 3` |
| **4. Non-Destructive Freshness** | `[:SUPERSEDES]` relationships preserve full corporate memory audit trail. | `python scripts/test_live_pipeline.py` |
| **5. Multi-Hop Dependency & Action** | Traverses blocker chains (`BLOCKED_BY`) and proposes human-confirmed actions. | `python scripts/test_mcp_client.py` |

---

## 📖 Key Documentation Links
- [System Architecture](ARCHITECTURE.md)
- [Graph Schema & Cypher Queries](SCHEMA.md)
- [Setup Instructions](SETUP.md)
- [36-Hour Hackathon Plan](TASKS.md)
- [Demo Presentation Script](DEMO_PLAN.md)
- [Current Project Status & Evidence](STATUS.md)

