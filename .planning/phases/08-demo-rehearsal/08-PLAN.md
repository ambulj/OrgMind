# Plan: Phase 08 — Demo Rehearsal, 3-Minute Video Recording & Backup Packaging

**Phase:** Phase 08  
**Milestone:** Milestone 4 — Rehearsal, Backup Recording & Final Submission  
**Estimated Time:** Hours 22 – 36 (Feature freeze reached at Hour 22)  
**Status:** In Progress ◆  

---

## Objective

Execute the 3-minute presentation walkthrough according to `DEMO_PLAN.md`, verify the system under presentation conditions, capture an emergency backup video recording, and assemble all submission materials for judging.

---

## Tasks Breakdown

### Task 1: Complete 3-Minute Presenter Walkthrough
- **Presenter A (Graph Architect)**:
  - 0:00 – 0:35: Hook on "Corporate Amnesia", FalkorDB graph architecture (163 nodes, 267 edges), OpenCypher range indexes.
  - 1:45 – 2:20: Announce the live Paynova failure event, explain non-destructive superseding, and trigger Moment C.
  - 2:45 – 3:00: Summary of business value and closing statement.
- **Presenter B (Agent & Full-Stack Architect)**:
  - 0:35 – 1:10: Trigger Moment A (Ownership & Weighted Expertise — Alice Chen, 14.0 pts).
  - 1:10 – 1:45: Trigger Moment B (Decision Lineage & Source Provenance — `SRC_DOC_PKCE_01` quote).
  - 2:20 – 2:45: Trigger Moment D (Draft vs Decision — Rohan's unheeded dissenting advice).
  - 2:45 – 3:00: Trigger Moment E (Multi-hop Blocker Analysis — `TICK-202` blocked by `TICK-201`) + show Action Confirmation card.
- **Verification Command**:
  ```powershell
  python scripts/preflight.py
  ```

### Task 2: Baseline Reset & Health Gate
- **Description**: Ensure the graph is restored to its pristine 163-node state before the presentation or recording.
- **Action**:
  ```powershell
  python scripts/reset_demo.py
  python -c "from orgmind.db import get_graph; g = get_graph(); print('Nodes:', len(g.query('MATCH (n) RETURN n').result_set))"
  ```
- **Success Criteria**: Exactly 163 nodes, 267 edges in `northwind_labs`.

### Task 3: Screen Capture Backup Video Recording
- **Description**: Record a crisp 1080p 3-minute screen capture of the full Demo Ribbon sequence (`demo_backup.mp4`).
- **Emergency Contingency**: If live Wi-Fi or local Docker encounters latency during live judging, immediately transition to the backup recording.
- **Artifact**: `demo_backup.mp4` / YouTube or Google Drive submission link.

### Task 4: Submission Package Verification
- **Description**: Confirm all required submission artifacts are linked and up to date:
  - [x] Repository README with setup instructions and judging criteria matrix
  - [x] Preflight script (`scripts/preflight.py`)
  - [x] 14-Question Benchmark Suite (`tests/test_questions.json`)
  - [x] FastMCP Server & Client tests (`scripts/test_mcp_client.py`)
  - [x] System Architecture diagram & Schema docs (`ARCHITECTURE.md`, `SCHEMA.md`)
  - [x] Presentation script (`DEMO_PLAN.md`)
  - [x] Verified Status & Test Evidence (`STATUS.md`)

---

## Execution Gates

1. **Gate 1 (Preflight)**: `scripts/preflight.py` returns 6/6 `🟢 PASS`.
2. **Gate 2 (Latency)**: Demo moments complete within the 3-minute presentation budget.
3. **Gate 3 (Grounded Refusal)**: Off-topic queries consistently return `"I couldn't find this in the company graph."` with zero hallucinations.
