# OrgMind 3-Minute Hackathon Demo Script

> **Goal**: Deliver a tight, compelling 3-minute presentation demonstrating the 4 core competencies of Track 3: Ownership, Decision Provenance, Real-Time Freshness/Superseding, and Simulated Action.

---

## ⏱️ Timing & Presenter Roles

* **Total Time**: 3 Minutes (180 seconds).
* **Person A (Graph Architect)**: Introduces the problem, explains the FalkorDB knowledge graph structure, and triggers the live update event.
* **Person B (Agent Architect)**: Operates the Streamlit UI, narrates the agent's tool reasoning, citations, and actions.

---

## 🎬 4 Demo Moments Walkthrough

### 0:00 – 0:30 | Hook & Architecture (Person A)
* **Spoken Pitch**:
  > *"Every growing company suffers from corporate amnesia. Critical architecture decisions get buried in random Google Docs, ownership is scattered across Jira, and context gets lost in Slack.  
  > Meet **OrgMind**, our autonomous Company Brain. We ingested Northwind Labs' docs, tickets, and chats into **FalkorDB** as a single connected knowledge graph. Let's see how OrgMind eliminates knowledge silos."*
* **Visual**: Show Streamlit UI and the live Pyvis graph visualization in the right panel showing interconnected People, Teams, Projects, and Decisions.

---

### 0:30 – 1:15 | Moment A: Ownership & Who-Knows (Person B)
* **Action**: Click `Moment A` button or type:
  > *"Who owns the OAuth Upgrade project, and who knows the most about OAuth?"*
* **Agent Response**:
  > *"The OAuth 2.1 & Keycloak Migration project (`PRJ_OAUTH_UPGRADE`) is owned by the **Platform & Auth** team, led by **Alice Chen** (`P_ALICE`).  
  > Based on authorship of specifications and review contributions, **Alice Chen** has the highest demonstrated expertise on OAuth (3 evidence records), followed by **Bob Martinez**."*
* **Key Point to Highlight to Judges**:
  > *"Notice that OrgMind didn't guess. It queried our graph to find the formal owner and ranked experts based on factual authorship evidence."*

---

### 1:15 – 1:50 | Moment B: Decision Trace with Verbatim Source (Person B)
* **Action**: Click `Moment B` button or type:
  > *"What database did we decide to use for billing reconciliation, and what is the exact source?"*
* **Agent Response**:
  > *"On 2026-01-20, Bob Martinez and Carol Danvers decided to use **PostgreSQL** for transaction reconciliation [Source: `SRC_DOC_BILL_01`]."*
* **Visual**: Highlight the right-hand **Verified Sources & Citations** panel. Show the verbatim quote from `data/docs/billing_migration.md`:
  > *"Database chosen for transaction reconciliation is PostgreSQL."*
* **Key Point to Highlight to Judges**:
  > *"Every single fact is bound to an immutable `Source` node with exact file paths and offsets. Zero hallucinations."*

---

### 1:50 – 2:30 | Moment C: Live Freshness & Superseding (Person A & Person B)
* **Action**: Person A announces an engineering shift:
  > *"Now imagine our backend team realizes PostgreSQL can't handle complex multi-currency audits, and they decide to switch to FalkorDB today."*
* **Action**: Click `Moment C: Live Supersede Event`. (This triggers `ingest_live_decision()`, loading `data/live/new_billing_decision.json` into FalkorDB in real time).
* **Agent Prompt**:
  > *"What is our current decision on billing reconciliation database, and what did it supersede?"*
* **Agent Response**:
  > *"The **current** decision (as of 2026-02-15) is to switch transaction reconciliation to **FalkorDB graph-state** [Source: `SRC_LIVE_DEC_BILLING_02`].  
  > This **supersedes** the previous decision (`DEC_BILLING_2026_01`) from 2026-01-20, which originally selected PostgreSQL [Source: `SRC_DOC_BILL_01`]."*
* **Key Point to Highlight to Judges**:
  > *"We didn't delete the old record! OrgMind preserves corporate lineage by creating a `[:SUPERSEDES]` relationship and marking the old decision superseded. The company brain retains its history."*

---

### 2:30 – 3:00 | Moment D: Simulated Company Action (Person B)
* **Action**: Click `Moment D` button or type:
  > *"Draft a message to #backend-eng letting them know about the billing switch to FalkorDB, and create a follow-up ticket."*
* **Agent Response**:
  > *"I have completed both actions:  
  > 1. Drafted message to `#backend-eng`: 'Team: Transaction reconciliation is moving from PostgreSQL to FalkorDB to support multi-currency graph audits.' [Simulated ID: `MSG-SIM-8412`]  
  > 2. Created ticket in `PRJ_BILLING_STRIPE`: 'Migrate transaction reconciliation store to FalkorDB' [Simulated ID: `TICK-SIM-3921`].  
  > Both actions are recorded directly into the knowledge graph."*
* **Closing Sentence (Person A)**:
  > *"OrgMind isn't just a search engine — it is an active participant that understands company state, traces decisions, and helps teams get work done. Thank you!"*

---

## 🛡️ Emergency Fallback Plan (If Live Demo Glitches)

If the local Docker container hangs or LLM API rate limits during the presentation:
1. **Fallback 1 (Instant Backup Video)**: Switch immediately to the 3-minute pre-recorded screen capture video (`demo_backup.mp4` recorded during Hour 30).
2. **Fallback 2 (Cached Output Mode)**: The Streamlit app includes pre-cached responses in `st.session_state` if FalkorDB connection drops.
3. **Fallback 3 (Direct Cypher Display)**: Open FalkorDB Browser at `http://localhost:3000` to show the graph visual directly in Redis.
