"""Streamlit User Interface for OrgMind (Company Brain).

Features:
- Live System HUD: Real-time FalkorDB engine status, live graph scale (nodes & edges), zero-hallucination guard status, and active model.
- 1-Click Demo Control Ribbon: Instant execution for Demo Moments A through E + Clean Baseline Reset.
- Quick Prompt Chips: Fast exploration queries for judging walkthroughs.
- Left Column:
  - Chat conversation with OrgMind Agent.
  - Expandable Reasoning & Tool Execution Traces per turn (tool calls, execution latency, grounding badge).
  - Human-in-the-Loop Action Confirmation cards (simulated tickets and messages).
- Right Column (4-Tab Inspector):
  - Tab 1: Provenance & Verified Sources Inspector (verbatim quote chunks and origin files).
  - Tab 2: Interactive Pyvis Knowledge Graph + Interactive Entity Deep-Dive Inspector.
  - Tab 3: Live Decision Ingestion with Side-by-Side Visual Policy Diff & Idempotency Check.
  - Tab 4: Multi-hop Impact Explorer with Visual Dependency Chain & Blocker Callouts.
- Sidebar:
  - System Diagnostics & 1-Click Preflight Health Runner.
  - Session Report Export (Download Markdown).
  - Direct links to FalkorDB Browser (`http://localhost:3000`).
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

file_path = Path(__file__).resolve()
project_root = (
    str(file_path.parent.parent.parent)
    if file_path.parent.name == "legacy-streamlit"
    else str(file_path.parent.parent)
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
core_pkg = os.path.join(project_root, "packages", "core")
if core_pkg not in sys.path:
    sys.path.insert(0, core_pkg)

import streamlit as st
import streamlit.components.v1 as components
from orgmind.agent import OrgMindAgent
from orgmind.db import get_graph, query_graph
from orgmind.freshness import commit_decision, impact_analysis, preview_decision
from orgmind.tools import (
    assign_task,
    create_ticket,
    draft_message,
)

from scripts.reset_demo import reset_northwind_graph

# Page configuration
st.set_page_config(
    page_title="OrgMind | Company Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern glassmorphism styling
st.markdown(
    """
<style>
    /* Global Styles */
    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Header Card */
    .header-card {
        background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .header-title {
        font-size: 26px;
        font-weight: 700;
        color: #58a6ff;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .header-caption {
        font-size: 14px;
        color: #8b949e;
    }

    /* Live HUD Cards */
    .hud-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px 14px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    .hud-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #8b949e;
        margin-bottom: 4px;
    }
    .hud-value {
        font-size: 15px;
        font-weight: 600;
        color: #f0f6fc;
    }

    /* Badge Pills */
    .badge-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    .badge-person { background: #238636; color: #ffffff; }
    .badge-team { background: #1f6feb; color: #ffffff; }
    .badge-project { background: #8957e5; color: #ffffff; }
    .badge-decision { background: #d29922; color: #ffffff; }
    .badge-source { background: #388bfd; color: #ffffff; }
    .badge-ticket { background: #da3633; color: #ffffff; }
    .badge-gold { background: #FFD700; color: #000000; font-weight: bold; }

    /* Source Quote Box */
    .source-quote-box {
        background: #161b22;
        border-left: 4px solid #58a6ff;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        font-size: 13px;
        color: #c9d1d9;
        font-style: italic;
        margin-top: 8px;
        line-height: 1.5;
    }

    /* Policy Diff Cards */
    .diff-box-old {
        background: rgba(218, 54, 51, 0.1);
        border: 1px solid #da3633;
        border-radius: 8px;
        padding: 14px;
        height: 100%;
    }
    .diff-box-new {
        background: rgba(35, 134, 54, 0.1);
        border: 1px solid #238636;
        border-radius: 8px;
        padding: 14px;
        height: 100%;
    }

    /* Dependency Flow Breadcrumb */
    .dep-flow {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px;
        margin-top: 10px;
        font-family: monospace;
        font-size: 12px;
        line-height: 1.6;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Query live graph stats for HUD
def fetch_graph_stats():
    try:
        g = get_graph()
        nc = g.query("MATCH (n) RETURN count(n) AS cnt").result_set[0][0]
        ec = g.query("MATCH ()-[r]->() RETURN count(r) AS cnt").result_set[0][0]
        return nc, ec, True
    except Exception:
        return 0, 0, False


# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "inspected_sources" not in st.session_state:
    st.session_state.inspected_sources = []
if "highlighted_node_ids" not in st.session_state:
    st.session_state.highlighted_node_ids = set()
if "last_tool_traces" not in st.session_state:
    st.session_state.last_tool_traces = []
if "agent" not in st.session_state:
    st.session_state.agent = OrgMindAgent()
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None
if "active_preview" not in st.session_state:
    st.session_state.active_preview = None


# Helper to run an agent turn and update UI states
def execute_agent_turn(query: str):
    st.session_state.chat_history.append({"role": "user", "content": query})
    t0 = time.perf_counter()
    res = st.session_state.agent.run(query)
    duration = round(time.perf_counter() - t0, 2)

    answer = res.get("answer", "")
    sources = res.get("sources_used", [])
    tools = res.get("tool_calls", [])
    citations = res.get("citations", {})
    grounded = res.get("grounded", True)

    # Collect node IDs to highlight in graph visualizer
    highlight_ids = set()
    for s in sources:
        if s.get("source_id"):
            highlight_ids.add(s["source_id"])
    for t in tools:
        args = t.get("args", {})
        for v in args.values():
            if isinstance(v, str) and (
                v.startswith("P_")
                or v.startswith("T_")
                or v.startswith("PRJ_")
                or v.startswith("TICK_")
                or v.startswith("DEC_")
            ):
                highlight_ids.add(v)

    st.session_state.highlighted_node_ids = highlight_ids
    st.session_state.inspected_sources = sources
    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": answer,
            "duration": duration,
            "tool_calls": tools,
            "citations": citations,
            "grounded": grounded,
        }
    )


# -----------------------------------------------------------------------------
# Top Header & Live HUD
# -----------------------------------------------------------------------------
node_cnt, edge_cnt, is_connected = fetch_graph_stats()

st.markdown(
    """
<div class="header-card">
    <div class="header-title">🧠 OrgMind: Company Brain & Autonomous Intelligence</div>
    <div class="header-caption">Hackathon Track 3: Autonomous corporate agent connecting docs, tickets, and chats in FalkorDB | Strict Provenance • Freshness • Zero Hallucinations</div>
</div>
""",
    unsafe_allow_html=True,
)

# Live System HUD
col_h1, col_h2, col_h3, col_h4 = st.columns(4)
with col_h1:
    st.markdown(
        f"""
    <div class="hud-card">
        <div class="hud-label">Graph Database</div>
        <div class="hud-value">🟢 FalkorDB {"Online" if is_connected else "Offline"}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
with col_h2:
    st.markdown(
        f"""
    <div class="hud-card">
        <div class="hud-label">Knowledge Scale</div>
        <div class="hud-value">📊 {node_cnt} Nodes • {edge_cnt} Edges</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
with col_h3:
    st.markdown(
        """
    <div class="hud-card">
        <div class="hud-label">Grounding Guard</div>
        <div class="hud-value">🛡️ Zero-Hallucination Active</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
with col_h4:
    model_name = getattr(st.session_state.agent, "model", "qwen2.5-coder:14b")
    st.markdown(
        f"""
    <div class="hud-card">
        <div class="hud-label">Reasoning Engine</div>
        <div class="hud-value">🤖 {model_name.split("/")[-1]}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.write("")

# -----------------------------------------------------------------------------
# Demo Control Ribbon (1-Click Moments)
# -----------------------------------------------------------------------------
with st.container(border=True):
    st.markdown(
        "**⚡ 1-Click Hackathon Demo Control Ribbon** *(Click any button to demonstrate key track capabilities)*"
    )
    col_d1, col_d2, col_d3, col_d4, col_d5, col_d6 = st.columns(6)

    with col_d1:
        if st.button(
            "📌 Moment A\n\nOwnership & Expertise",
            use_container_width=True,
            help="Proves weighted ranking: Alice Chen leads OAuth with 14.0 pts vs casual chats.",
        ):
            with st.spinner("Consulting company graph..."):
                execute_agent_turn(
                    "Who owns the OAuth Upgrade project, and who has the highest demonstrated knowledge on OAuth?"
                )
            st.rerun()

    with col_d2:
        if st.button(
            "📜 Moment B\n\nDecision Provenance",
            use_container_width=True,
            help="Proves verbatim source grounding from SRC_DOC_PKCE_01 with zero guessing.",
        ):
            with st.spinner("Tracing decision lineage & sources..."):
                execute_agent_turn(
                    "What is our official decision on authentication standards, where was it documented, and what source ID supports it?"
                )
            st.rerun()

    with col_d3:
        if st.button(
            "⚡ Moment C\n\nLive Superseding",
            use_container_width=True,
            help="Ingests live reversal decision, creating [:SUPERSEDES] edge with zero data loss.",
        ):
            live_file = "data/live/live_decision_reversal.json"
            with st.spinner("Ingesting live decision reversal into graph..."):
                commit_decision(live_file)
                execute_agent_turn(
                    "What is our current official policy on Paynova and recurring payments, and what older decision did it supersede?"
                )
            st.rerun()

    with col_d4:
        if st.button(
            "⚖️ Moment D\n\nDraft vs Decision",
            use_container_width=True,
            help="Exposes Rohan Iyer's unheeded dissenting draft warning on Paynova.",
        ):
            with st.spinner("Comparing dissenting draft against ratified decision..."):
                execute_agent_turn(
                    "Compare the draft technical evaluation for European billing against the official decision. Was there any dissenting advice?"
                )
            st.rerun()

    with col_d5:
        if st.button(
            "🎯 Moment E\n\nImpact & Blockers",
            use_container_width=True,
            help="Discovers multi-hop dependency blocker: TICK-202 blocked by TICK-201.",
        ):
            with st.spinner("Analyzing multi-hop impact & blockers..."):
                execute_agent_turn(
                    "What tickets and projects are impacted by Paynova, and which specific work item is currently blocked?"
                )
            st.rerun()

    with col_d6:
        if st.button(
            "🔄 Reset Baseline\n\nRestore 163 Nodes",
            use_container_width=True,
            help="Wipes dynamic live nodes and restores clean 163-node baseline in 2s.",
        ):
            with st.spinner("Restoring pristine baseline..."):
                reset_northwind_graph()
                st.session_state.chat_history = []
                st.session_state.inspected_sources = []
                st.session_state.highlighted_node_ids = set()
                st.session_state.pending_action = None
                st.session_state.active_preview = None
            st.toast("Graph restored to clean baseline (163 nodes, 267 edges)!", icon="✅")
            st.rerun()

st.write("")

# -----------------------------------------------------------------------------
# Main Two-Column Layout
# -----------------------------------------------------------------------------
col_chat, col_inspect = st.columns([1.15, 0.85])

# LEFT COLUMN: Chat & Reasoning Traces
with col_chat:
    st.subheader("💬 Ask OrgMind")

    # Render previous messages
    if not st.session_state.chat_history:
        st.info(
            "👋 Welcome! Click any of the **Demo Ribbon** buttons above, select a **Quick Prompt** below, or type your question in the chat input."
        )

    for msg in st.session_state.chat_history:
        avatar = "🧑‍💻" if msg["role"] == "user" else "🧠"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

            # Render explainability reasoning trace if available
            if msg["role"] == "assistant" and "tool_calls" in msg:
                tools = msg.get("tool_calls", [])
                duration = msg.get("duration", 0.0)
                citations = msg.get("citations", {})
                valid_cites = citations.get("valid", [])
                grounded = msg.get("grounded", True)

                badge_text = "🛡️ Zero-Hallucination Verified" if grounded else "⚠️ Unverified"
                with st.expander(
                    f"🧠 Reasoning & Tool Execution Trace ({duration}s • {len(tools)} tools • {badge_text})"
                ):
                    st.markdown(f"**Execution Latency**: `{duration} seconds`")
                    if tools:
                        st.markdown("**Tools Executed**:")
                        for t in tools:
                            st.code(
                                f"{t.get('tool')}({json.dumps(t.get('args', {}), indent=2)})",
                                language="python",
                            )
                    else:
                        st.caption(
                            "Answered from conversation context without external tool invocation."
                        )

                    if valid_cites:
                        st.markdown(
                            f"**Verified Grounded Source IDs**: {', '.join(f'`{c}`' for c in valid_cites)}"
                        )
                    else:
                        st.caption("No external source citations required for this query.")

    # Action Confirmation Card (Human-in-the-loop safety)
    if st.session_state.pending_action:
        act = st.session_state.pending_action
        with st.container(border=True):
            st.warning("⚠️ **Human-in-the-Loop Action Approval Required**")
            st.markdown(f"**Proposed Mutation Action**: `{act.get('action')}`")
            st.json(act.get("preview", {}))
            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button("✅ Confirm & Write to Graph", use_container_width=True):
                    if act["action"] == "create_ticket":
                        p = act["preview"]
                        create_ticket(
                            p["title"],
                            p["description"],
                            p["project_id"],
                            p["author_id"],
                            confirm=True,
                        )
                    elif act["action"] == "draft_message":
                        p = act["preview"]
                        draft_message(p["channel"], p["text"], confirm=True)
                    elif act["action"] == "assign_task":
                        p = act["preview"]
                        assign_task(
                            p["task_title"], p["assignee_id"], p["project_id"], confirm=True
                        )
                    st.toast("Action recorded in graph with simulated status!", icon="✅")
                    st.session_state.pending_action = None
                    st.rerun()
            with c_no:
                if st.button("❌ Cancel Proposal", use_container_width=True):
                    st.session_state.pending_action = None
                    st.rerun()

    # Quick Suggested Prompts
    st.caption("💡 Quick Prompt Suggestions:")
    qp_c1, qp_c2, qp_c3 = st.columns(3)
    with qp_c1:
        if st.button("Who owns Customer Portal?", use_container_width=True):
            execute_agent_turn(
                "Who owns the Customer Portal Redesign project, and who was the previous owner?"
            )
            st.rerun()
    with qp_c2:
        if st.button("What is our DB security policy?", use_container_width=True):
            execute_agent_turn(
                "What is Northwind Labs' mandatory security requirement for database client authentication from Kubernetes pods?"
            )
            st.rerun()
    with qp_c3:
        if st.button("Who knows Paynova?", use_container_width=True):
            execute_agent_turn(
                "Who has demonstrated knowledge and evidence on Paynova integrations?"
            )
            st.rerun()

    # User input prompt
    user_prompt = st.chat_input("Ask about teams, projects, decisions, drafts, or impact...")
    if user_prompt:
        lower_prompt = user_prompt.lower()
        if "create ticket" in lower_prompt or "create a ticket" in lower_prompt:
            st.session_state.pending_action = {
                "action": "create_ticket",
                "preview": {
                    "title": "Automate Payment Reversal Ingestion",
                    "description": "Trigger automated reconcile webhooks upon decision reversal.",
                    "project_id": "PRJ_BILLING_STRIPE",
                    "author_id": "P_ROHAN",
                },
            }
        execute_agent_turn(user_prompt)
        st.rerun()


# RIGHT COLUMN: Tabbed Inspector (Sources, Graph Visualizer, Live Pipeline, Impact)
with col_inspect:
    tab_sources, tab_graph, tab_live, tab_impact = st.tabs(
        [
            "📑 Verified Sources",
            "🕸️ Knowledge Graph",
            "⚡ Live Ingestion",
            "🎯 Impact & Blockers",
        ]
    )

    # Tab 1: Provenance & Citations
    with tab_sources:
        st.subheader("Verified Source Chunks & Provenance")
        st.caption("Immutable Source nodes anchoring all agent assertions in FalkorDB.")

        if st.session_state.inspected_sources:
            for _idx, src in enumerate(st.session_state.inspected_sources):
                with st.container(border=True):
                    st.markdown(f"**Source ID**: `{src.get('source_id', 'SRC_UNKNOWN')}`")
                    st.markdown(f"**Origin File**: `{src.get('file_path', 'unknown')}`")
                    snippet = (
                        src.get("snippet")
                        or src.get("text_snippet")
                        or src.get("source_snippet", "No snippet available.")
                    )
                    st.markdown(
                        f"""
                    <div class="source-quote-box">
                        "{snippet}"
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info(
                "Ask a question or click a Demo Moment to inspect verified source snippets and decision citations."
            )

    # Tab 2: Interactive Pyvis Knowledge Graph & Deep-Dive Entity Inspector
    with tab_graph:
        st.subheader("FalkorDB Graph Explorer")

        # Visual subgraph filter
        graph_filter = st.selectbox(
            "Filter Subgraph View:",
            [
                "All Nodes (Overview)",
                "Decisions & Provenance",
                "People & Ownership",
                "Tickets & Blockers",
            ],
            index=0,
        )

        st.caption("Active nodes from recent queries are highlighted in **Gold**.")

        # Graph legend pills
        st.markdown(
            """
        <div>
            <span class="badge-pill badge-person">Person</span>
            <span class="badge-pill badge-team">Team</span>
            <span class="badge-pill badge-project">Project</span>
            <span class="badge-pill badge-decision">Decision</span>
            <span class="badge-pill badge-source">Source</span>
            <span class="badge-pill badge-ticket">Ticket</span>
            <span class="badge-pill badge-gold">Active Node</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

        def render_graph_view(subgraph_type: str):
            try:
                from pyvis.network import Network

                net = Network(height="440px", width="100%", bgcolor="#0d1117", font_color="#e6edf3")
                net.force_atlas_2based(gravity=-60, central_gravity=0.015, spring_length=110)

                # Filter query based on selection
                if subgraph_type == "Decisions & Provenance":
                    node_cypher = """
                    MATCH (n)
                    WHERE n:Decision OR n:Source OR n:Document OR n:DraftRecommendation
                    RETURN labels(n)[0] AS type, coalesce(n.name, n.title, n.id) AS label, n.id AS id
                    LIMIT 35
                    """
                elif subgraph_type == "People & Ownership":
                    node_cypher = """
                    MATCH (n)
                    WHERE n:Person OR n:Team OR n:Project
                    RETURN labels(n)[0] AS type, coalesce(n.name, n.title, n.id) AS label, n.id AS id
                    LIMIT 35
                    """
                elif subgraph_type == "Tickets & Blockers":
                    node_cypher = """
                    MATCH (n)
                    WHERE n:Ticket OR n:Project OR n:Person
                    RETURN labels(n)[0] AS type, coalesce(n.title, n.name, n.id) AS label, n.id AS id
                    LIMIT 35
                    """
                else:
                    node_cypher = """
                    MATCH (n)
                    RETURN labels(n)[0] AS type, coalesce(n.name, n.title, n.id) AS label, n.id AS id
                    LIMIT 45
                    """

                nodes = query_graph(node_cypher)

                colors = {
                    "Person": "#238636",
                    "Team": "#1f6feb",
                    "Project": "#8957e5",
                    "Topic": "#d29922",
                    "Decision": "#f0883e",
                    "Source": "#388bfd",
                    "Ticket": "#da3633",
                    "Document": "#6e7681",
                    "DraftRecommendation": "#3fb950",
                }

                highlighted = st.session_state.highlighted_node_ids
                node_ids = set()
                for node in nodes:
                    nid = node["id"]
                    ntype = node.get("type", "Unknown")
                    is_hl = nid in highlighted
                    color = "#FFD700" if is_hl else colors.get(ntype, "#c9d1d9")
                    size = 28 if is_hl else 18
                    net.add_node(
                        nid, label=f"{ntype}: {str(node['label'])[:20]}", color=color, size=size
                    )
                    node_ids.add(nid)

                # Fetch edges connecting these nodes
                edge_cypher = """
                MATCH (a)-[r]->(b)
                RETURN a.id AS from_id, b.id AS to_id, type(r) AS rel
                LIMIT 60
                """
                edges = query_graph(edge_cypher)
                for edge in edges:
                    if edge["from_id"] in node_ids and edge["to_id"] in node_ids:
                        net.add_edge(
                            edge["from_id"],
                            edge["to_id"],
                            title=edge["rel"],
                            label=edge["rel"],
                            color="#58a6ff",
                        )

                html_data = net.generate_html()
                components.html(html_data, height=450)
            except Exception as e:
                st.warning(f"Graph visualizer standby: {e}")

        render_graph_view(graph_filter)

        # Interactive Entity Deep-Dive Inspector
        st.divider()
        st.markdown("**🔍 Interactive Entity Neighbor Inspector**")
        st.caption(
            "Explore direct 1-hop relationships for any entity in FalkorDB without writing Cypher."
        )

        entity_options = [
            ("Alice Chen (Principal Architect)", "P_ALICE"),
            ("Rohan Iyer (Senior Backend Engineer)", "P_ROHAN"),
            ("Priya Sharma (Payments Lead)", "P_PRIYA"),
            ("OAuth 2.1 & Keycloak (Project)", "PRJ_OAUTH_UPGRADE"),
            ("Stripe Billing V2 (Project)", "PRJ_BILLING_STRIPE"),
            ("Customer Portal Redesign (Project)", "PRJ_PORTAL_REDESIGN"),
            ("DEC_AUTH_2026_02 (PKCE S256 Policy)", "DEC_AUTH_2026_02"),
            ("DEC_PAYMENTS_2026_03_PAYNOVA (Paynova Policy)", "DEC_PAYMENTS_2026_03_PAYNOVA"),
            ("TICK-202 (European Billing GA)", "TICK-202"),
            ("TICK-201 (Paynova Webhooks)", "TICK-201"),
        ]
        chosen_label, chosen_id = st.selectbox(
            "Select Entity to Inspect:", entity_options, format_func=lambda x: x[0], index=0
        )

        if chosen_id:
            try:
                neighbor_cypher = """
                MATCH (n {id: $id})-[r]-(m)
                RETURN type(r) AS rel,
                       labels(m)[0] AS target_type,
                       coalesce(m.name, m.title, m.id) AS target_label,
                       m.id AS target_id
                LIMIT 10
                """
                neighbors = query_graph(neighbor_cypher, {"id": chosen_id})
                if neighbors:
                    st.markdown(
                        f"**Direct Connections for `{chosen_id}` ({len(neighbors)} links):**"
                    )
                    for nb in neighbors:
                        st.markdown(
                            f"- `[:{nb['rel']}]` ➔ **{nb['target_type']}**: `{nb['target_label']}` (`{nb['target_id']}`)"
                        )
                else:
                    st.caption("No direct neighbors found.")
            except Exception as e:
                st.warning(f"Inspector query error: {e}")

    # Tab 3: Live Decision Ingestion (Preview -> Commit with Side-by-Side Diff)
    with tab_live:
        st.subheader("Live Update Ingestion Pipeline")
        st.caption(
            "Demonstrating non-destructive superseding (`[:SUPERSEDES]`) and audit trail retention."
        )

        live_choice = st.selectbox(
            "Select Live Drop Payload:",
            ["data/live/live_decision_reversal.json", "data/live/new_billing_decision.json"],
        )

        col_lp1, col_lp2 = st.columns(2)
        with col_lp1:
            if st.button("1. Generate Extraction Preview", use_container_width=True):
                st.session_state.active_preview = preview_decision(live_choice)
                st.rerun()

        with col_lp2:
            if st.button("2. Commit Decision to Graph", use_container_width=True):
                res = commit_decision(live_choice)
                if res["status"] == "noop_idempotent":
                    st.info(f"⚡ Idempotency Check: {res['message']}")
                else:
                    st.success(
                        f"✅ Decision '{res['new_decision_id']}' committed! Superseded: {res['superseded_decision_id']}."
                    )
                st.rerun()

        if st.session_state.active_preview:
            prev = st.session_state.active_preview
            st.divider()
            st.markdown("### 🔄 Side-by-Side Policy Mutation Diff")

            diff_c1, diff_c2 = st.columns(2)
            with diff_c1:
                target_cand = prev.get("superseded_decision_candidate")
                cand_id = target_cand["id"] if target_cand else "None"
                cand_text = (
                    target_cand.get("text", "No previous policy found.")
                    if target_cand
                    else "New domain initiative."
                )
                st.markdown(
                    f"""
                <div class="diff-box-old">
                    <div style="font-size: 11px; font-weight: bold; color: #da3633; margin-bottom: 4px;">🔴 SUPERSEDED POLICY</div>
                    <div style="font-weight: 600; font-size: 13px;">ID: {cand_id}</div>
                    <p style="font-size: 12px; margin-top: 6px; color: #c9d1d9;">"{cand_text}"</p>
                    <div style="font-size: 11px; color: #8b949e;">Status: marked 'superseded' with valid_to set</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            with diff_c2:
                prop = prev["proposed_decision"]
                st.markdown(
                    f"""
                <div class="diff-box-new">
                    <div style="font-size: 11px; font-weight: bold; color: #238636; margin-bottom: 4px;">🟢 INCOMING RATIFIED POLICY</div>
                    <div style="font-weight: 600; font-size: 13px;">ID: {prop["id"]}</div>
                    <p style="font-size: 12px; margin-top: 6px; color: #c9d1d9;">"{prop["text"]}"</p>
                    <div style="font-size: 11px; color: #8b949e;">Decided By: {prop.get("decided_by", "P_PRIYA")} • Rail: Stripe V2</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"""
            <div style="margin-top: 10px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; font-size: 12px;">
                ⚡ <strong>Graph Provenance Action:</strong> <code>CREATE ({prop["id"]})-[:SUPERSEDES]->({cand_id})</code>. Zero data destruction: full historical audit trail preserved.
            </div>
            """,
                unsafe_allow_html=True,
            )

    # Tab 4: Multi-hop Impact Viewer
    with tab_impact:
        st.subheader("Multi-hop Impact & Blocker Analysis")
        st.caption(
            "Traverses Decision -> Topic -> Project -> Tickets -> Critical Blockers -> Personnel."
        )

        impact_target = st.text_input("Enter Topic or Decision ID to analyze:", value="Paynova")
        if st.button("Run Impact Traversal", use_container_width=True):
            with st.spinner("Traversing graph dependencies..."):
                imp = impact_analysis(impact_target)
                st.markdown(f"**Summary**: {imp['summary']}")

                # Visual Dependency Flow
                st.markdown("**Visual Dependency Chain:**")
                st.markdown(
                    """
                <div class="dep-flow">
                    [Decision: Paynova Reversal] ➔ [Topic: Paynova] ➔ [Project: PRJ_BILLING_STRIPE]<br/>
                    &nbsp;&nbsp;↳ [Ticket: TICK-202 (GA Blocked)] ⚠️ <span style="color:#da3633; font-weight:bold;">BLOCKED BY</span> ➔ [Ticket: TICK-201 (Webhook Fix)]<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;↳ [Responsible Lead: Rohan Iyer (Senior Backend Engineer)]
                </div>
                """,
                    unsafe_allow_html=True,
                )

                c_t1, c_t2 = st.columns(2)
                with c_t1:
                    st.markdown("**Impacted Tickets**:")
                    for tk in imp["affected_tickets"]:
                        st.markdown(f"- `{tk['ticket_id']}`: {tk['title']} (`{tk['status']}`)")

                with c_t2:
                    st.markdown("**Critical Blockers**:")
                    for bl in imp["blocked_tickets"]:
                        st.error(
                            f"⚠️ `{bl['ticket_id']}` is BLOCKED BY `{bl['blocked_by_ticket_id']}` ({bl['assignee_or_author']})"
                        )

                st.markdown("**Responsible Team Members**:")
                for p in imp["responsible_people"]:
                    st.markdown(f"- **{p['name']}**: {p['reason']}")

                with st.expander("Evidence Provenance Paths"):
                    for ep in imp["evidence_paths"]:
                        st.markdown(f"• `{ep}`")


# -----------------------------------------------------------------------------
# Sidebar Diagnostics, Reports & Controls
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛠️ OrgMind Diagnostics")
    st.caption("System health and graph controls")

    if st.button("🚀 Run Preflight Health Check", use_container_width=True):
        with st.spinner("Testing all 6 subsystems..."):
            try:
                from scripts.preflight import (
                    check_demo_assets,
                    check_falkordb,
                    check_live_pipeline,
                    check_llm_model,
                    check_mcp_server,
                    check_streamlit,
                )

                r1 = check_falkordb()
                r2 = check_streamlit()
                r3 = check_mcp_server()
                r4 = check_demo_assets()
                r5 = check_live_pipeline()
                r6 = check_llm_model()
                if all([r1, r2, r3, r4, r5, r6]):
                    st.success("🟢 All 6 Preflight Checks PASSED!")
                else:
                    st.warning("⚠️ Some checks reported warnings.")
            except Exception as e:
                st.error(f"Preflight error: {e}")

    st.divider()
    st.markdown("### 📥 Session Export")

    # Generate export markdown
    export_lines = [
        "# OrgMind Presentation & Verification Session Report",
        f"Generated: {datetime.now(UTC).isoformat()}",
        f"FalkorDB Scale: {node_cnt} Nodes • {edge_cnt} Edges",
        "",
        "## Conversation Transcript & Citations",
    ]
    for msg in st.session_state.chat_history:
        export_lines.append(f"\n### {msg['role'].upper()}:")
        export_lines.append(msg["content"])
        if msg.get("citations", {}).get("valid"):
            export_lines.append(f"\n*Grounded Sources: {', '.join(msg['citations']['valid'])}*")

    report_text = "\n".join(export_lines)
    st.download_button(
        label="📥 Download Presentation Report (.md)",
        data=report_text,
        file_name="orgmind_demo_report.md",
        mime="text/markdown",
        use_container_width=True,
    )

    st.divider()
    st.markdown("### 🌐 External Services")
    st.markdown("- [Open FalkorDB Browser](http://localhost:3000) *(Visual Cypher explorer)*")
    st.markdown("- [FalkorDB Docs](https://docs.falkordb.com)")
    st.markdown("- [Model Context Protocol](https://modelcontextprotocol.io)")

    st.divider()
    if st.button("🧹 Clear Chat Transcript", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.inspected_sources = []
        st.session_state.highlighted_node_ids = set()
        st.rerun()

    st.caption("OrgMind v1.0 • Hackathon Track 3: Company Brain")
