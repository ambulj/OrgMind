# Archived: Legacy Streamlit Prototype (`apps/legacy-streamlit`)

> [!NOTE]
> As of Phase 7 / Phase 8 milestone completion, the Streamlit prototype in `apps/legacy-streamlit/streamlit_app.py` has been **formally archived**.
> The production frontend is the enterprise Next.js 14 web application in `apps/web`.

---

## Feature Parity Matrix

All features originally designed in Streamlit have reached full parity and enterprise expansion in `apps/web`:

| Feature | Legacy Streamlit (`apps/legacy-streamlit`) | Production Web App (`apps/web`) |
| :--- | :--- | :--- |
| **Question Answering** | Blocking generation with markdown footer | **Streaming SSE** with real-time reasoning steps (`step`, `tool_call`, `token`) |
| **Citation Grounding** | Text footer citation checks | **3-Layer Validator Badge** (`ok`, `repaired`, `blocked`) + interactive slide-over citation drawer |
| **Knowledge Graph** | In-memory Pyvis HTML iframe | **Cytoscape.js** interactive canvas with neighborhood hops, shortest semantic path, and node inspector |
| **Decision Lineage** | Static table of decisions | **Supersession Tree** with bitemporal dates (`valid_from`, `valid_to`) and cryptographic source anchors |
| **Review Queue** | Basic button in sidebar | **Human-in-the-Loop Hub** with side-by-side Before/After diffs and downstream impact modal |
| **Ingestion** | Direct Python script run | **File Upload Connector** (.md, .txt, .pdf), sample seed trigger, and job queue status table |
| **Governance & Safety**| Console prints | **Immutable Audit Log** viewer with role-gated queries (Auditor/Admin) |
| **Design System** | Default Streamlit styling | **Next.js 14 + Tailwind CSS + Lucide**, WCAG 2.2 AA compliant high-contrast theme |

---

## Running the Legacy Prototype (For Historical Reference Only)

If you need to inspect the original prototype:
```bash
python -m streamlit run apps/legacy-streamlit/streamlit_app.py --server.port 8501
```

For all ongoing development, use:
```bash
cd apps/web
npm run dev
```
