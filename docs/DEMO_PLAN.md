# OrgMind 3-Minute Hackathon Demo Script & Presentation Guide

> **Goal**: Deliver a tight, compelling 3-minute presentation demonstrating the 5 core judging pillars of Track 3:
> 1. Unified Graph (Docs, Tickets, Chats in FalkorDB)
> 2. Ownership & Demonstrated Expertise Ranking
> 3. Decision Lineage & Source Provenance
> 4. Non-Destructive Freshness (`[:SUPERSEDES]`)
> 5. Dissenting Draft Analysis & Multi-Hop Impact

---

## ⏱️ Timing & Presenter Roles

* **Total Duration**: 3 Minutes (180 seconds).
* **Person A (Graph Architect)**: Introduces the corporate amnesia problem, highlights FalkorDB graph modeling, triggers the live superseding update, and concludes.
* **Person B (Agent Architect)**: Operates the Streamlit UI, narrates agent tool execution, demonstrates verified source citations, and highlights multi-hop blocker chains.

---

## 🎬 5 Demo Moments Walkthrough

### 0:00 – 0:35 | Hook & Architecture (Person A)
* **Spoken Pitch**:
  > *"Every growing company suffers from corporate amnesia. Critical architecture decisions get buried in random Google Docs, ticket ownership is scattered, and key context vanishes in Slack channels.  
  > Meet **OrgMind**, our autonomous Company Brain. We ingested Northwind Labs' docs, tickets, and chats into **FalkorDB** as a single connected knowledge graph. With 163 nodes, OpenCypher range indexes, and an autonomous tool-calling agent, OrgMind makes company memory instantly queryable and verifiable."*
* **Visual**: Show Streamlit interface (`http://localhost:8501`), highlighting the top Demo Control Bar and the interactive Pyvis Knowledge Graph in the right pane.

---

### 0:35 – 1:10 | Moment A: Ownership & Weighted Expertise (Person B)
* **Action**: Click `Moment A: Ownership & Expertise` on the Demo Control Ribbon.
* **Agent Query**:
  > *"Who owns the OAuth Upgrade project, and who has the highest demonstrated knowledge on OAuth?"*
* **Agent Response**:
  > *"The OAuth 2.1 & Keycloak Migration project (`PRJ_OAUTH_UPGRADE`) is owned by the **Platform & Auth** team, led by **Alice Chen** (`P_ALICE`).  
  > Based on weighted graph evidence across architectural specs, tickets, and review contributions, **Alice Chen** ranks #1 with 14.0 evidence points."*
* **Key Point to Highlight to Judges**:
  > *"Notice OrgMind doesn't guess or suffer from near-ties. It evaluated weighted evidence (specs = 3.0 pts, tickets = 2.0 pts, chats = 1.0 pt) directly from the graph to distinguish authoritative leads from casual chat participants."*

---

### 1:10 – 1:45 | Moment B: Decision Lineage & Source Provenance (Person B)
* **Action**: Click `Moment B: Decision Provenance`.
* **Agent Query**:
  > *"What is our official decision on authentication standards, where was it documented, and what source ID supports it?"*
* **Agent Response**:
  > *"Northwind Labs officially enforces **OAuth 2.1 with PKCE** backed by Keycloak, strictly requiring S256 code challenge methods (`DEC_AUTH_2026_02`). Documented in `oauth_pkce_spec.md` [Source: `SRC_DOC_PKCE_01`]."*
* **Visual**: Click over to **Tab 1: Verified Sources** in the right column. Point out the verbatim text chunk and exact file path.
* **Key Point to Highlight to Judges**:
  > *"Every single claim is grounded to an immutable `Source` node with a verified SHA-256 hash in FalkorDB. If no verified source exists in the company graph, the agent deterministically refuses to answer."*

---

### 1:45 – 2:20 | Moment C: Live Freshness & Superseding (Person A & Person B)
* **Spoken Pitch (Person A)**:
  > *"Now imagine an engineering crisis happens live: Paynova's payment gateway starts dropping transactions in Europe, and management issues an emergency reversal decision today."*
* **Action**: Click `Moment C: Live Superseding`.
* **What Happens Under the Hood**:
  - The live pipeline validates `data/live/live_decision_reversal.json`.
  - Links the new decision (`DEC_PAYMENTS_2026_05_REVERSAL`) to the older decision via `[:SUPERSEDES]`.
  - Sets `valid_to` timestamp on the superseded decision without deleting it.
* **Agent Response**:
  > *"The current active policy as of 2026-05-30 is to **freeze and reverse Paynova integration** [Source: `SRC_LIVE_REVERSAL_PAYNOVA_01`]. This **superseded** the prior decision from 2026-03-01 (`DEC_PAYMENTS_2026_03_PAYNOVA`) [Source: `SRC_DOC_PAYNOVA_DECISION_01`]."*
* **Key Point to Highlight to Judges**:
  > *"Zero data destruction. OrgMind preserves complete corporate history and audit trails through graph relationships."*

---

### 2:20 – 2:45 | Moment D: Dissenting Draft vs Ratified Policy (Person B)
* **Action**: Click `Moment D: Draft vs Decision`.
* **Agent Query**:
  > *"Compare the draft technical evaluation for European billing against the official decision. Was there any dissenting advice?"*
* **Agent Response**:
  > *"Yes. On 2026-02-24, senior engineer **Rohan Iyer** submitted draft recommendation `DRAFT_PAYNOVA_EVAL` warning that Paynova lacked robust multi-currency idempotency and advising against adoption. However, on 2026-03-01, Priya Sharma ratified policy `DEC_PAYMENTS_2026_03_PAYNOVA` adopting Paynova. The unheeded warning directly foreshadowed incident INC-409."*
* **Key Point to Highlight to Judges**:
  > *"OrgMind can surface unheeded technical dissenting drafts, giving leadership complete visibility into decision risk."*

---

### 2:45 – 3:00 | Moment E: Multi-Hop Impact & Actions (Person A & Person B)
* **Action**: Click `Moment E: Impact & Blocker`.
* **Agent Response**:
  > *"Traversed 3 impacted tickets across Billing. Critical finding: `TICK-202` ('Implement Paynova SEPA Direct Debit') is currently **BLOCKED BY** `TICK-201` ('Resolve Paynova webhook signature verification'). Responsible engineer: Rohan Iyer."*
* **Action Safety Card**: Show the Human-in-the-Loop Action Approval card in the UI before committing simulated tickets or messages.
* **Closing Pitch (Person A)**:
  > *"OrgMind isn't just a search engine — it is an autonomous corporate intelligence system that understands ownership, traces decisions, predicts impact, and safeguards institutional knowledge. Thank you!"*

---

## 🛡️ Presentation Fallback & Emergency Plan

1. **Fallback 1 (Pre-recorded Backup Video)**: `demo_backup.mp4` ready for instant full-screen playback if network fails.
2. **Fallback 2 (1-Click Reset)**: Click `🔄 Reset Baseline` on the top ribbon to instantly wipe and restore FalkorDB to its 163-node baseline.
3. **Fallback 3 (Preflight Verification)**: Run `python scripts/preflight.py` 10 minutes before judging starts to ensure all 6 subsystems are green.
