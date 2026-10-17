# OrgMind (Company Brain) — Hackathon Track 3

## What This Is

OrgMind is an autonomous corporate intelligence agent and company brain built on FalkorDB. It ingests Northwind Labs' architecture docs, Jira tickets, and Slack communications into a single unified knowledge graph, enabling employees and leadership to answer questions, trace decision provenance back to exact document chunks, resolve project ownership and demonstrated expertise without ties, track non-destructive decision superseding in real time, and safely propose actions with human-in-the-loop confirmation.

## Core Value

Connect documents, tickets, and chats into ONE FalkorDB knowledge graph so an autonomous agent can answer company questions with cryptographic source provenance, zero hallucinations, and live freshness.

## Hackathon Context & Track Alignment

- **Track**: Track 3 ("Build an agent that understands how a company works").
- **Judging Focus Areas**:
  1. Unified Graph: Docs, tickets, and chats in one FalkorDB graph.
  2. Who Owns & Who Knows: Exact leads and weighted expertise evidence.
  3. Decision Provenance: Every assertion backed by immutable `Source` nodes.
  4. Non-Destructive Freshness: Historical lineage preserved via `[:SUPERSEDES]`.
  5. Action Safety & Multi-Hop Impact: Propose-then-confirm workflows and blocker discovery.

## UI Redesign Objective

Elevate the user interface in `app/streamlit_app.py` to a production-grade hackathon presentation standard with:
- Glassmorphism dark theme styling and custom CSS tokens
- Live HUD status indicators (DB connectivity, 163 nodes, 267 edges, zero-hallucination guard)
- 1-Click Demo Control Ribbon covering Moments A through E + Reset
- Interactive Pyvis knowledge graph with subgraph filtering (Lineage, Ownership, Blockers)
- Side-by-side live decision diff viewer
- Visual multi-hop dependency and blocker tree

## Key Decisions

| Decision | Rationale | Outcome |
| :--- | :--- | :--- |
| **FalkorDB OpenCypher** | Extreme low-latency graph traversals on Redis core; range indexes for sub-10ms queries. | ✓ Good |
| **LiteLLM Provider-Agnostic ReAct** | Works with local Ollama (`qwen2.5-coder:14b`) and cloud LLMs seamlessly. | ✓ Good |
| **Immutable Source Nodes** | Eliminates hallucinations by anchoring all answers to verbatim text chunks. | ✓ Good |
| **Non-Destructive Superseding** | Updates link `[:SUPERSEDES]` without deleting older decisions, preserving corporate audit trail. | ✓ Good |
| **Glassmorphism Dark UI** | Maximizes visual impact during 3-minute hackathon demo presentation. | ✓ Good |

---
*Last updated: 2026-10-17 after Phase 9 & UI Redesign Initialization*
