---
title: OrgMind
emoji: 🧠
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🧠 OrgMind: Enterprise Company Brain & Knowledge Graph Platform

[![Monorepo](https://img.shields.io/badge/Monorepo-Packages%20%26%20Apps-blue.svg)](#)
[![Graph Database](https://img.shields.io/badge/Graph-FalkorDB%20(OpenCypher)-red.svg)](https://docs.falkordb.com)
[![App Database](https://img.shields.io/badge/App%20DB-PostgreSQL%2016-blue.svg)](https://www.postgresql.org)
[![Worker Queue](https://img.shields.io/badge/Worker-arq%20%2B%20Redis%207-darkgreen.svg)](https://arq-docs.helpmanual.io/)
[![API](https://img.shields.io/badge/API-FastAPI%20(REST%20%26%20SSE)-teal.svg)](https://fastapi.tiangolo.com)
[![Web](https://img.shields.io/badge/Frontend-Next.js%2014%20%2B%20Tailwind%20%2B%20Cytoscape-black.svg)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](#)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)](#)

> **OrgMind** connects people, teams, projects, documents, tickets, chats, and decisions in a unified enterprise knowledge graph powered by **FalkorDB**. A grounded agent coordinates answering organizational questions with SHA-256 verified citation tracking, bitemporal decision history, live freshness supersession, and role-gated two-phase actions.

---

## 🏛️ Target Architecture & Monorepo Layout

OrgMind is structured as a clean, enterprise monorepo:

```text
├── packages/
│   └── core/                     # Reusable orgmind domain package
│       ├── orgmind/
│       │   ├── agent.py          # Provider-agnostic LiteLLM tool loop with grounding validator
│       │   ├── auth.py           # Multi-tenant RBAC (Admin, Editor, Viewer, Auditor) & JWT
│       │   ├── config.py         # Type-safe pydantic-settings configuration
│       │   ├── db.py             # FalkorDB connection pool & parameterized Cypher query runner
│       │   ├── freshness.py      # Bitemporal decision supersession & multi-hop impact analysis
│       │   ├── ingest/           # 8-stage retryable pipeline & connector interfaces
│       │   ├── models.py         # SQLAlchemy app models (Workspaces, Users, AuditLog, ReviewItem)
│       │   ├── resolve.py        # Entity resolution with alias merging and unknown handle flags
│       │   ├── tools.py          # Allow-listed Cypher query tools
│       │   └── mcp_server.py     # FastMCP tool server with 11 standard enterprise tools
│       └── pyproject.toml
│
├── apps/
│   ├── api/                      # FastAPI v1 REST & SSE streaming server
│   │   ├── main.py               # Application entrypoint & global error envelope
│   │   ├── routes/               # Modular routes: /ask, /graph, /decisions, /reviews, etc.
│   │   ├── dependencies.py       # Role gating & workspace context injectors
│   │   └── schemas.py            # Strict Pydantic v2 contract schemas
│   │
│   ├── web/                      # Next.js 14 Enterprise Web Application
│   │   ├── src/app/              # App Router: Ask Brain, Graph Explorer, Decision Lineage, Reviews
│   │   ├── src/lib/              # Typed SSE streaming client & API utilities
│   │   └── package.json          # Next.js 14, React 18, Tailwind CSS, Cytoscape.js
│   │
│   ├── worker/                   # Background asynchronous worker (arq + Redis)
│   │   └── main.py               # Worker entrypoint running pipeline ingestion jobs
│   │
│   └── legacy-streamlit/         # Archived Streamlit prototype (kept for reference)
│       ├── streamlit_app.py
│       └── ARCHIVED.md           # Archival notice & feature parity matrix
│
├── infra/                        # Infrastructure & container configs
│   ├── docker-compose.yml        # Multi-container orchestration (FalkorDB, Postgres, Redis, API, Web)
│   └── Dockerfile.api            # Production containerfile for API & Worker
│
├── data/                         # Synthetic baseline dataset (Northwind Labs)
│   ├── people.csv, teams.csv, projects.csv, tickets.json
│   ├── docs/                     # Architecture Decision Records (.md)
│   ├── chats/                    # Communication transcripts (.jsonl)
│   └── live/                     # Live decision update payloads
│
├── docs/                         # Architecture, API specifications, and governance
│   ├── API.md                    # Detailed API endpoint reference
│   ├── openapi.json              # Exported OpenAPI 3.1 schema (24 endpoints)
│   ├── CONNECTORS.md             # Enterprise connector contracts (Slack, Drive, Jira, GitHub)
│   ├── MIGRATIONS.md             # Alembic & FalkorDB migration guides
│   ├── ARCHITECTURE.md           # System architecture & Mermaid flow diagrams
│   └── SETUP.md                  # Development environment setup guide
│
├── scripts/                      # Operational utilities
│   ├── smoke_test.py             # FalkorDB & Cypher smoke verification
│   ├── preflight.py              # 7-subsystem automated health check
│   ├── backup_restore.py         # Per-graph JSON dump and restore tool
│   └── reset_demo.py             # Safe database reset to clean baseline
│
├── tests/                        # 48 Automated unit, security & ingestion tests
│   ├── test_api.py               # FastAPI endpoint contract & SSE streaming tests
│   ├── test_prompt_injection.py  # Security suite verifying untrusted delimiters & citation blocks
│   ├── test_ingestion_service.py # Pipeline idempotency, file upload & review queue tests
│   └── run_eval.py               # 24-question benchmark evaluation harness
│
├── Makefile                      # Standardized developer task runner
├── pyproject.toml                # Monorepo dependencies & tool configs (Ruff, Mypy, Pytest)
└── STATUS.md                     # Honest truth audit & acceptance verification logs
```

---

## ⚡ Global Enterprise Rules

1. **Evidence-Based Acceptance**: Never claim "done" without executing acceptance commands and recording real output in [`STATUS.md`](file:///c:/Users/sauja/Downloads/New%20folder/STATUS.md).
2. **OpenCypher Subset Compliance**: Parameterize all queries against FalkorDB; end-users never execute raw Cypher queries.
3. **Never Delete History**: Superseding updates `status="superseded"` and `valid_to`. Deletions use **Redaction Tombstones** (blank Source text, keep graph structure, log who/when/why).
4. **Verified Citation Grounding**: Every answer claim must cite a Source ID that exists in FalkorDB, was returned by a tool in that turn, and is visible to the caller's role. Citations carry verified SHA-256 source hashes and file origins.
5. **Untrusted Data Boundary**: Documents and chat transcripts are untrusted data. Tool outputs and extraction inputs are enclosed in strict delimiters (`=== BEGIN UNTRUSTED DATA ===`) with prompt-injection defense.
6. **Two-Phase Action Governance**: Mutating actions (`create_ticket`, `draft_message`, `assign_task`) are propose-then-confirm, role-gated, and logged to an immutable audit log.
7. **Clear Synthetic Labeling**: Synthetic sample datasets are clearly marked across the UI (`Synthetic Baseline: Northwind Labs`).

---

## 🏆 Hackathon Submission Metadata

- **Public Source-Code Repository**: [https://github.com/ambulj/OrgMind](https://github.com/ambulj/OrgMind)
- **Track**: **Track 3: Graph RAG, Autonomous Agents & Enterprise Knowledge Graphs**
- **Demo Video**: [OrgMind 3-Minute Presentation Walkthrough](https://github.com/ambulj/OrgMind#demo-video) (Script and moment timestamps: [`docs/DEMO_PLAN.md`](docs/DEMO_PLAN.md))
- **Deployment Mode**: Full local setup instructions via Docker Compose (`docker compose --profile fullstack up`) or developer CLI (`make setup && make dev-api`).

---

## 📊 Graph Data Model

OrgMind models organizational memory inside **FalkorDB** as a property graph with 10 first-class node types and 12 directed relationship types.

```mermaid
graph TD
    Person["Person<br/>(id, name, role, email)"]
    Team["Team<br/>(id, name)"]
    Project["Project<br/>(id, name, status)"]
    Decision["Decision<br/>(id, text, topic, status,<br/>valid_from, valid_to, confidence)"]
    Draft["DraftRecommendation<br/>(id, topic, recommendation, date)"]
    Source["Source<br/>(id, file_path, text_snippet,<br/>content_hash, visibility, redacted)"]
    Ticket["Ticket<br/>(id, title, status, priority)"]
    Doc["Document<br/>(id, path, title)"]
    Topic["Topic<br/>(name)"]
    Msg["Message<br/>(id, channel, content, timestamp)"]

    Person -->|MEMBER_OF| Team
    Person -->|LEADS| Team
    Person -->|OWNS {valid_from, valid_to, status}| Project
    Team -->|OWNS {valid_from, valid_to, status}| Project
    Person -->|DECIDED_BY| Decision
    Person -->|AUTHORED| Draft
    Person -->|AUTHORED| Ticket
    Person -->|AUTHORED| Msg
    Person -->|ASSIGNED_TO| Ticket

    Decision -->|DERIVED_FROM| Source
    Decision -->|ABOUT| Topic
    Decision -->|SUPERSEDES {superseded_at}| Decision
    Draft -->|DERIVED_FROM| Source
    Draft -->|ABOUT| Topic
    Doc -->|CONTAINS_DRAFT| Draft

    Ticket -->|ABOUT| Topic
    Ticket -->|PART_OF| Project
    Ticket -->|BLOCKED_BY| Ticket
    Ticket -->|DEPENDS_ON| Project
    Msg -->|ABOUT| Topic
```

### Key Schema Properties & Bitemporality

| Entity / Rel | Key Properties | Bitemporal / Governance Rules |
| :--- | :--- | :--- |
| **`(:Decision)`** | `id`, `text`, `topic`, `status`, `valid_from`, `valid_to`, `recorded_at`, `confidence`, `review_status` | Status is `'current'` or `'superseded'`. `valid_from`/`valid_to` track real-world policy validity, while `recorded_at` tracks system ingestion time. |
| **`(:Source)`** | `id`, `file_path`, `chunk_offset`, `text_snippet`, `content_hash`, `visibility`, `redacted`, `redacted_at` | Anchored by SHA-256 `content_hash`. Non-destructive redactions use tombstones (`redacted=true`) keeping topology. |
| **`(:Person)`** | `id`, `name`, `role`, `email`, `handle` | Resolved via exact handles and fuzzy aliases (`resolve.py`). Unknown actors are queued for review; never auto-created as phantom nodes. |
| **`[r:OWNS]`** | `valid_from`, `valid_to`, `recorded_at`, `status` | Bitemporal ownership tenure. Previous owners transition to `status='previous'` with `valid_to` stamped upon handoff. |
| **`[r:SUPERSEDES]`** | `superseded_at` | Created strictly when a newer decision replaces an older one on the same topic (`old.valid_from < timestamp`). |

---

## ⚡ Core Cypher Queries & Graph Algorithms

OrgMind executes parameterized OpenCypher queries against FalkorDB with zero raw Cypher exposed to users.

### 1. Bitemporal Ownership Query (with Point-in-Time `as_of` Filtering)
Finds active or historical project owners based on real-world validity intervals:
```cypher
MATCH (owner)-[r:OWNS]->(target)
WHERE target.id = $project_id OR target.name = $project_name
RETURN owner.id AS owner_id,
       owner.name AS owner_name,
       labels(owner)[0] AS owner_type,
       r.status AS status,
       r.valid_from AS valid_from,
       r.valid_to AS valid_to
ORDER BY r.valid_from DESC
```

### 2. Weighted Domain Knowledge Scoring Graph Aggregation
Computes dynamic expertise rankings across technical specifications, decisions, tickets, and chat communications:
```cypher
MATCH (p:Person)-[:AUTHORED]->(item)-[:MENTIONS|ABOUT]->(top:Topic {name: $topic})
OPTIONAL MATCH (item)-[:DERIVED_FROM]->(src:Source)
WHERE src IS NULL OR (NOT src.redacted AND (src.visibility = 'all' OR src.visibility CONTAINS ('"' + $caller_role + '"') OR $caller_role = 'Admin'))
RETURN p.id AS person_id,
       p.name AS person_name,
       p.role AS role,
       labels(item)[0] AS item_type,
       item.id AS item_id
UNION
MATCH (p:Person)-[:ASSIGNED_TO]->(tk:Ticket)-[:ABOUT]->(top:Topic {name: $topic})
RETURN p.id AS person_id, p.name AS person_name, p.role AS role, 'AssignedTicket' AS item_type, tk.id AS item_id
```
*Algorithm*: Scores: Architecture Specs/Decisions = 3.0 pts, Authored Tickets = 2.0 pts, Assigned Tickets = 1.5 pts, Chat Evidence = 1.0 pt.

### 3. Multi-Hop Dynamic Impact & Blocker Traversal
Traverses graph dependencies to determine every ticket and project impacted when a decision is reversed or superseded:
```cypher
MATCH (d:Decision)-[:ABOUT]->(top:Topic {name: $topic})
OPTIONAL MATCH (tk:Ticket)-[:ABOUT]->(top)
OPTIONAL MATCH (tk)-[:BLOCKED_BY*1..3]->(blocked_tk:Ticket)
OPTIONAL MATCH (tk)-[:PART_OF|DEPENDS_ON]->(prj:Project)
RETURN d.id AS decision_id,
       collect(DISTINCT tk.id) AS directly_affected_tickets,
       collect(DISTINCT blocked_tk.id) AS downstream_blocked_tickets,
       collect(DISTINCT prj.name) AS affected_projects
```

### 4. Non-Destructive Decision Supersession Mutation
Safely marks old decisions as superseded and links them to replacement policies with date guards:
```cypher
OPTIONAL MATCH (old:Decision)
WHERE (($supersedes_id IS NOT NULL AND old.id = $supersedes_id)
   OR ($supersedes_id IS NULL AND (toLower(old.topic) = toLower($topic) OR (old)-[:ABOUT]->(:Topic {name: $topic}))
       AND old.id <> $decision_id AND (old.valid_from IS NULL OR old.valid_from < $timestamp)))
  AND old.status = 'current'
SET old.status = "superseded", old.valid_to = $timestamp

MERGE (src:Source {id: $source_id})
SET src.file_path = $source_file, src.text_snippet = $source_snippet, src.content_hash = $content_hash,
    src.visibility = '["all"]', src.redacted = false, src.valid_from = $timestamp

MERGE (new:Decision {id: $decision_id})
SET new.topic = $topic, new.text = $text, new.status = "current", new.valid_from = $timestamp,
    new.confidence = 1.0, new.confidence_tier = "High", new.review_status = "approved"

MERGE (new)-[:DERIVED_FROM]->(src)
MERGE (top:Topic {name: $topic})
MERGE (new)-[:ABOUT]->(top)

FOREACH (_ IN CASE WHEN old IS NOT NULL THEN [1] ELSE [] END |
    CREATE (new)-[:SUPERSEDES {superseded_at: $timestamp}]->(old)
)
```

### 5. Permission-Aware Citation & Neighborhood Traversal
Explores up to $N$ hops around an entity while preventing data leakage of confidential or redacted sources:
```cypher
MATCH (start)
WHERE start.id = $entity OR toLower(start.name) = toLower($entity)
MATCH path = (start)-[*1..2]-(neighbor)
WHERE labels(neighbor)[0] <> 'Source' OR (
    NOT coalesce(neighbor.redacted, false) AND 
    (neighbor.visibility = 'all' OR neighbor.visibility = '["all"]' OR neighbor.visibility CONTAINS ('"' + $caller_role + '"') OR $caller_role = 'Admin')
)
RETURN DISTINCT labels(neighbor)[0] AS neighbor_type,
                neighbor.id AS neighbor_id,
                coalesce(neighbor.name, neighbor.title, neighbor.text, neighbor.id) AS label,
                neighbor.status AS status,
                length(path) AS distance
LIMIT 60
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: 18+ (tested on Node 20 / 24)
- **Docker**: For running FalkorDB, PostgreSQL, and Redis

### 2. Local Setup
```bash
# Clone the repository
cd "New folder"

# Set up Python virtual environment
python -m venv venv
.\venv\Scripts\activate       # On Windows
# source venv/bin/activate     # On Mac/Linux

# Install dependencies in editable mode
make setup

# Configure environment variables
copy .env.example .env
```

### 3. Start Database Containers
```bash
docker compose up -d falkordb postgres redis
```

### 4. Run Tests & Preflight
```bash
# Execute the complete 48-test suite
make test

# Run the 7-point subsystem preflight check
make preflight
```

### 5. Launch Fullstack Development Environment
```bash
# Terminal 1: Launch FastAPI backend (port 8000)
make dev-api

# Terminal 2: Launch Next.js web application (port 3000)
make dev-web

# Terminal 3: Launch arq background worker
make dev-worker
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser.

---

## 🌐 Fullstack Docker Compose Deployment

To deploy the entire production stack in Docker with one command:

```bash
docker compose --profile fullstack up --build
```

| Service | Container Name | Port | Description |
| :--- | :--- | :--- | :--- |
| **FalkorDB** | `orgmind_falkordb` | `6379`, `3002` | Primary Knowledge Graph with AOF/RDB persistence |
| **PostgreSQL** | `orgmind_postgres` | `5432` | Relational store for users, workspaces, jobs & audit logs |
| **Redis** | `orgmind_redis_jobs` | `6380` | Dedicated queue for background ingestion worker |
| **FastAPI** | `orgmind_api` | `8000` | REST & SSE API with Swagger UI at `/docs` |
| **Worker** | `orgmind_worker` | - | Asynchronous pipeline ingestion worker (`arq`) |
| **Next.js Web** | `orgmind_web` | `3000` | Production React 18 web application |

---

## 🧪 Testing & Verification Suites

```bash
# Run all unit, security & integration tests
pytest tests/ -v

# Run prompt-injection defense suite
pytest tests/test_prompt_injection.py -v

# Run 24-question benchmark evaluation harness
python tests/run_eval.py --limit 10

# Code quality & type checks
make lint
make typecheck
```

---

## 🔒 Security & RBAC Matrix

| Role | Ask Brain | Graph Explorer | Upload Docs | Approve Reviews | Execute Actions | View Audit Log |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Editor** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Viewer** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Auditor**| ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |

---

## 📚 Key Documentation

- [`docs/API.md`](docs/API.md): API documentation for all REST & SSE streaming endpoints.
- [`docs/openapi.json`](docs/openapi.json): Full OpenAPI 3.1 contract specification.
- [`docs/CONNECTORS.md`](docs/CONNECTORS.md): Specifications for Slack, Google Drive, Jira, and GitHub.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Architectural topology and data flow diagrams.
- [`docs/MIGRATIONS.md`](docs/MIGRATIONS.md): Alembic database migrations and FalkorDB graph schema evolution.
- [`STATUS.md`](STATUS.md): Complete truth audit and verification command outputs across all phases.
