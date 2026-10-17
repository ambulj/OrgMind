"""Streamlit User Interface for OrgMind (Company Brain).

Features:
- Demo Control Ribbon: 1-click execution for Demo Moments A through E + Clean Reset.
- Left Column:
  - Chat conversation with OrgMind Agent.
  - Expandable Reasoning & Tool Execution Trace per turn (tool calls, latency, grounding status).
  - Action Confirmation cards (Human-in-the-loop safety).
- Right Column:
  - Tab 1: Provenance & Citations Inspector (verbatim quote chunks and source metadata).
  - Tab 2: Interactive Pyvis Knowledge Graph with active path highlighting.
  - Tab 3: Live Decision Ingestion (Preview -> Impact -> Commit with Idempotency).
  - Tab 4: Multi-hop Impact Explorer (Decision -> Topic -> Project -> Tickets -> Blockers).
"""

import streamlit as st
import json
import os
import sys
import time
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit.components.v1 as components
from orgmind.agent import OrgMindAgent
from orgmind.freshness import preview_decision, commit_decision, impact_analysis
from orgmind.tools import (
    trace_decision,
    who_owns,
    who_knows_about,
    compare_draft_vs_decision,
    create_ticket,
    draft_message,
    assign_task,
)
from orgmind.db import query_graph
from scripts.reset_demo import reset_northwind_graph

# Page configuration
st.set_page_config(
    page_title="OrgMind | Company Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🧠 OrgMind: Company Brain & Autonomous Agent")
st.caption("Hackathon Track 3: Autonomous corporate agent over FalkorDB graph | Provenance • Freshness • Zero Hallucinations")

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
            if isinstance(v, str) and (v.startswith("P_") or v.startswith("T_") or v.startswith("PRJ_") or v.startswith("TICK_")):
                highlight_ids.add(v)

    st.session_state.highlighted_node_ids = highlight_ids
    st.session_state.inspected_sources = sources
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer,
        "duration": duration,
        "tool_calls": tools,
        "citations": citations,
        "grounded": grounded,
    })


# -----------------------------------------------------------------------------
# Demo Control Ribbon
# -----------------------------------------------------------------------------
with st.expander("⚡ Hackathon Demo Control Bar (1-Click Moments)", expanded=True):
    col_d1, col_d2, col_d3, col_d4, col_d5, col_d6 = st.columns(6)

    with col_d1:
        if st.button("Moment A: Ownership & Expertise", use_container_width=True):
            with st.spinner("Consulting company graph..."):
                execute_agent_turn("Who owns the OAuth Upgrade project, and who has the highest demonstrated knowledge on OAuth?")
            st.rerun()

    with col_d2:
        if st.button("Moment B: Decision Provenance", use_container_width=True):
            with st.spinner("Tracing decision lineage & sources..."):
                execute_agent_turn("What is our official decision on authentication standards, where was it documented, and what source ID supports it?")
            st.rerun()

    with col_d3:
        if st.button("Moment C: Live Superseding", use_container_width=True):
            live_file = "data/live/live_decision_reversal.json"
            preview = preview_decision(live_file)
            st.session_state.live_preview = preview
            with st.spinner("Ingesting live decision reversal into graph..."):
                commit_decision(live_file)
                execute_agent_turn("What is our current official policy on Paynova and recurring payments, and what older decision did it supersede?")
            st.rerun()

    with col_d4:
        if st.button("Moment D: Draft vs Decision", use_container_width=True):
            with st.spinner("Comparing dissenting draft against ratified decision..."):
                execute_agent_turn("Compare the draft technical evaluation for European billing against the official decision. Was there any dissenting advice?")
            st.rerun()

    with col_d5:
        if st.button("Moment E: Impact & Blocker", use_container_width=True):
            with st.spinner("Analyzing multi-hop impact & blockers..."):
                execute_agent_turn("What tickets and projects are impacted by Paynova, and which specific work item is currently blocked?")
            st.rerun()

    with col_d6:
        if st.button("🔄 Reset Baseline", use_container_width=True):
            with st.spinner("Wiping graph and restoring clean baseline..."):
                reset_northwind_graph()
                st.session_state.chat_history = []
                st.session_state.inspected_sources = []
                st.session_state.highlighted_node_ids = set()
                st.session_state.pending_action = None
            st.success("Graph restored to clean baseline (163 nodes, 267 edges)!")
            st.rerun()

st.divider()

# -----------------------------------------------------------------------------
# Main Two-Column Layout
# -----------------------------------------------------------------------------
col_chat, col_inspect = st.columns([1.1, 0.9])

# LEFT COLUMN: Chat & Reasoning Traces
with col_chat:
    st.subheader("💬 Ask OrgMind")

    # Render previous messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Render explainability reasoning trace if available
            if msg["role"] == "assistant" and "tool_calls" in msg:
                tools = msg.get("tool_calls", [])
                duration = msg.get("duration", 0.0)
                citations = msg.get("citations", {})
                valid_cites = citations.get("valid", [])
                grounded = msg.get("grounded", True)

                with st.expander(f"🧠 Reasoning Trace ({duration}s • {len(tools)} tools • {'🛡️ Grounded' if grounded else '⚠️ Review'})"):
                    st.markdown(f"**Execution Latency**: `{duration} seconds`")
                    if tools:
                        st.markdown("**Tools Called**:")
                        for t in tools:
                            st.code(f"{t.get('tool')}({json.dumps(t.get('args', {}))})", language="python")
                    else:
                        st.caption("Responded directly without tool delegation.")

                    if valid_cites:
                        st.markdown(f"**Verified Grounded Sources**: {', '.join(f'`{c}`' for c in valid_cites)}")
                    else:
                        st.caption("No external source citations required for this query.")

    # Action Confirmation Card (Human-in-the-loop safety)
    if st.session_state.pending_action:
        act = st.session_state.pending_action
        with st.container(border=True):
            st.warning("⚠️ **Action Execution Approval Required**")
            st.markdown(f"**Proposed Action**: `{act.get('action')}`")
            st.json(act.get("preview", {}))
            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button("✅ Confirm & Write to Graph"):
                    if act["action"] == "create_ticket":
                        p = act["preview"]
                        create_ticket(p["title"], p["description"], p["project_id"], p["author_id"], confirm=True)
                    elif act["action"] == "draft_message":
                        p = act["preview"]
                        draft_message(p["channel"], p["text"], p["author_id"], confirm=True)
                    elif act["action"] == "assign_task":
                        p = act["preview"]
                        assign_task(p["task_title"], p["assignee_id"], p["project_id"], confirm=True)
                    st.success("Action recorded in graph with simulated status!")
                    st.session_state.pending_action = None
                    st.rerun()
            with c_no:
                if st.button("❌ Cancel"):
                    st.session_state.pending_action = None
                    st.rerun()

    # User input prompt
    user_prompt = st.chat_input("Ask about teams, projects, decisions, drafts, or impact...")
    if user_prompt:
        # Check if user is asking to create or draft something (action safety demonstration)
        lower_prompt = user_prompt.lower()
        if "create ticket" in lower_prompt or "create a ticket" in lower_prompt:
            st.session_state.pending_action = {
                "action": "create_ticket",
                "preview": {
                    "title": "Automate Payment Reversal Ingestion",
                    "description": "Trigger automated reconcile webhooks upon decision reversal.",
                    "project_id": "PRJ_BILLING_STRIPE",
                    "author_id": "P_ROHAN",
                }
            }
        execute_agent_turn(user_prompt)
        st.rerun()


# RIGHT COLUMN: Tabbed Inspector (Sources, Graph Visualizer, Live Pipeline, Impact)
with col_inspect:
    tab_sources, tab_graph, tab_live, tab_impact = st.tabs([
        "📑 Verified Sources",
        "🕸️ Knowledge Graph",
        "⚡ Live Update Pipeline",
        "🎯 Impact & Blockers",
    ])

    # Tab 1: Provenance & Citations
    with tab_sources:
        st.subheader("Verified Source Chunks")
        if st.session_state.inspected_sources:
            for idx, src in enumerate(st.session_state.inspected_sources):
                with st.container(border=True):
                    st.markdown(f"**Source ID**: `{src.get('source_id', 'SRC_UNKNOWN')}`")
                    st.markdown(f"**Origin File**: `{src.get('file_path', 'unknown')}`")
                    st.caption("Verbatim Quote Chunk:")
                    st.info(f"\"{src.get('text_snippet', src.get('snippet', 'No snippet text.'))}\"")
        else:
            st.info("Ask a question to inspect verified source snippets and decision citations.")

    # Tab 2: Interactive Pyvis Knowledge Graph
    with tab_graph:
        st.subheader("FalkorDB Graph Explorer")
        st.caption("Active nodes from recent turns are highlighted in gold.")

        def render_graph_view():
            try:
                from pyvis.network import Network
                net = Network(height="450px", width="100%", bgcolor="#0E1117", font_color="white")
                net.force_atlas_2based()

                # Query sample nodes from graph
                cypher = """
                MATCH (n)
                RETURN labels(n)[0] AS type,
                       coalesce(n.name, n.title, n.id) AS label,
                       n.id AS id
                LIMIT 40
                """
                nodes = query_graph(cypher)

                colors = {
                    "Person": "#4CAF50",
                    "Team": "#2196F3",
                    "Project": "#9C27B0",
                    "Topic": "#FF9800",
                    "Decision": "#E91E63",
                    "Source": "#00BCD4",
                    "Ticket": "#FFC107",
                    "Document": "#607D8B",
                    "DraftRecommendation": "#00E676",
                }

                highlighted = st.session_state.highlighted_node_ids
                for node in nodes:
                    nid = node["id"]
                    ntype = node.get("type", "Unknown")
                    is_hl = nid in highlighted
                    color = "#FFD700" if is_hl else colors.get(ntype, "#FFFFFF")
                    size = 28 if is_hl else 18
                    net.add_node(nid, label=f"{ntype}: {node['label'][:22]}", color=color, size=size)

                # Query edges
                edge_cypher = """
                MATCH (a)-[r]->(b)
                RETURN a.id AS from_id, b.id AS to_id, type(r) AS rel
                LIMIT 50
                """
                edges = query_graph(edge_cypher)
                for edge in edges:
                    if edge["from_id"] and edge["to_id"]:
                        net.add_edge(edge["from_id"], edge["to_id"], title=edge["rel"], label=edge["rel"])

                html_data = net.generate_html()
                components.html(html_data, height=480)
            except Exception as e:
                st.warning(f"Graph visualizer standby: {e}")

        render_graph_view()

    # Tab 3: Live Decision Ingestion (Preview -> Commit)
    with tab_live:
        st.subheader("Live Update Ingestion Pipeline")
        st.caption("Demonstrating non-destructive superseding and idempotency.")

        live_choice = st.selectbox(
            "Select Live Drop Payload:",
            [
                "data/live/live_decision_reversal.json",
                "data/live/new_billing_decision.json"
            ]
        )

        col_lp1, col_lp2 = st.columns(2)
        with col_lp1:
            if st.button("1. Generate Extraction Preview"):
                st.session_state.active_preview = preview_decision(live_choice)
                st.rerun()

        with col_lp2:
            if st.button("2. Commit Decision to Graph"):
                res = commit_decision(live_choice)
                if res["status"] == "noop_idempotent":
                    st.info(f"⚡ Idempotency Check: {res['message']}")
                else:
                    st.success(f"✅ Decision '{res['new_decision_id']}' committed! Superseded: {res['superseded_decision_id']}.")
                st.rerun()

        if "active_preview" in st.session_state and st.session_state.active_preview:
            prev = st.session_state.active_preview
            with st.container(border=True):
                st.markdown(f"**Proposed Mutation Action**: `{prev.get('action')}`")
                st.markdown(f"**Target Decision ID**: `{prev['proposed_decision']['id']}`")
                st.markdown(f"**Supersedes Candidate**: `{prev['superseded_decision_candidate']['id'] if prev.get('superseded_decision_candidate') else 'None (New Decision)'}`")
                st.markdown(f"**Text**: *{prev['proposed_decision']['text']}*")
                st.caption(f"Source: {prev['source'].get('file_path')}")

    # Tab 4: Multi-hop Impact Viewer
    with tab_impact:
        st.subheader("Multi-hop Impact Analysis")
        st.caption("Traverses Decision -> Topic -> Project -> Tickets -> Blockers -> People.")

        impact_target = st.text_input("Enter Topic or Decision ID to analyze:", value="Paynova")
        if st.button("Run Impact Traversal"):
            with st.spinner("Traversing graph dependencies..."):
                imp = impact_analysis(impact_target)
                st.markdown(f"**Summary**: {imp['summary']}")

                c_t1, c_t2 = st.columns(2)
                with c_t1:
                    st.markdown("**Impacted Tickets**:")
                    for tk in imp["affected_tickets"]:
                        st.markdown(f"- `{tk['ticket_id']}`: {tk['title']} (`{tk['status']}`)")

                with c_t2:
                    st.markdown("**Critical Blockers**:")
                    for bl in imp["blocked_tickets"]:
                        st.error(f"⚠️ `{bl['ticket_id']}` is BLOCKED BY `{bl['blocked_by_ticket_id']}` ({bl['assignee_or_author']})")

                st.markdown("**Responsible Team Members**:")
                for p in imp["responsible_people"]:
                    st.markdown(f"- **{p['name']}**: {p['reason']}")

                with st.expander("Evidence Provenance Paths"):
                    for ep in imp["evidence_paths"]:
                        st.markdown(f"• `{ep}`")
