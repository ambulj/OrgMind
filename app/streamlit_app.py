"""Streamlit User Interface for OrgMind (Company Brain).

Features:
- Left Column: Chat conversation with OrgMind Agent.
- Right Column:
  - Source Provenance Inspector (displays verified text quotes for Source IDs).
  - Interactive Knowledge Graph visualization using Pyvis.
- Top Demo Bar: 1-click buttons to trigger the 4 Hackathon Demo moments.
"""

import streamlit as st
import json
import os
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit.components.v1 as components
from orgmind.agent import OrgMindAgent
from orgmind.freshness import ingest_live_decision
from orgmind.tools import trace_decision, who_owns, who_knows_about
from orgmind.db import query_graph

# Page configuration
st.set_page_config(
    page_title="OrgMind | Company Brain",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 OrgMind: Company Brain & Knowledge Graph")
st.caption("Track 3: Autonomous Company Agent connected to FalkorDB Graph")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "inspected_sources" not in st.session_state:
    st.session_state.inspected_sources = []
if "agent" not in st.session_state:
    st.session_state.agent = OrgMindAgent()

# -----------------------------------------------------------------------------
# Demo Action Ribbon
# -----------------------------------------------------------------------------
with st.expander("⚡ Hackathon Demo Control Bar (1-Click Moments)", expanded=True):
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)

    with col_d1:
        if st.button("Moment A: Who Owns & Knows"):
            q = "Who owns the OAuth Upgrade project, and who knows the most about OAuth?"
            st.session_state.chat_history.append({"role": "user", "content": q})
            with st.spinner("Consulting company graph..."):
                res = st.session_state.agent.run(q)
                st.session_state.chat_history.append({"role": "assistant", "content": res["answer"]})
                st.session_state.inspected_sources = res["sources_used"]
            st.rerun()

    with col_d2:
        if st.button("Moment B: Trace Billing Decision"):
            q = "What database did we decide to use for billing reconciliation, and what is the source?"
            st.session_state.chat_history.append({"role": "user", "content": q})
            with st.spinner("Tracing decision lineage..."):
                res = st.session_state.agent.run(q)
                st.session_state.chat_history.append({"role": "assistant", "content": res["answer"]})
                st.session_state.inspected_sources = res["sources_used"]
            st.rerun()

    with col_d3:
        if st.button("Moment C: Live Supersede Event"):
            try:
                update_result = ingest_live_decision()
                st.success(f"Live Update Ingested! Decision {update_result['new_decision_id']} superseded {update_result['superseded_decision_id']}.")
                q = "What is our current decision on billing reconciliation database, and what did it supersede?"
                st.session_state.chat_history.append({"role": "user", "content": q})
                res = st.session_state.agent.run(q)
                st.session_state.chat_history.append({"role": "assistant", "content": res["answer"]})
                st.session_state.inspected_sources = res["sources_used"]
            except Exception as e:
                st.error(f"Live update failed: {e}")
            st.rerun()

    with col_d4:
        if st.button("Moment D: Simulated Action"):
            q = "Draft a message to #backend-eng letting the team know about the billing reconciliation switch to FalkorDB, and create a follow-up ticket."
            st.session_state.chat_history.append({"role": "user", "content": q})
            with st.spinner("Executing simulated graph actions..."):
                res = st.session_state.agent.run(q)
                st.session_state.chat_history.append({"role": "assistant", "content": res["answer"]})
            st.rerun()

st.divider()

# -----------------------------------------------------------------------------
# Main Two-Column Layout
# -----------------------------------------------------------------------------
col_chat, col_inspect = st.columns([1.1, 0.9])

# LEFT COLUMN: Chat
with col_chat:
    st.subheader("💬 Ask OrgMind")

    # Render previous messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # User input prompt
    user_prompt = st.chat_input("Ask about teams, projects, decisions, or recent changes...")
    if user_prompt:
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge graph..."):
                response = st.session_state.agent.run(user_prompt)
                st.markdown(response["answer"])
                st.session_state.chat_history.append({"role": "assistant", "content": response["answer"]})
                st.session_state.inspected_sources = response["sources_used"]
        st.rerun()


# RIGHT COLUMN: Source Provenance & Graph Visualizer
with col_inspect:
    st.subheader("📑 Verified Sources & Citations")
    if st.session_state.inspected_sources:
        for idx, src in enumerate(st.session_state.inspected_sources):
            with st.container(border=True):
                st.markdown(f"**Source ID**: `{src.get('source_id', 'SRC_UNKNOWN')}`")
                st.markdown(f"**Origin File**: `{src.get('file_path', 'unknown')}`")
                st.caption("Verbatim Quote Chunk:")
                st.info(f"\"{src.get('text_snippet', src.get('source_snippet', 'No snippet available.'))}\"")
    else:
        st.info("Ask a question to inspect verified source snippets and decision citations.")

    st.divider()
    st.subheader("🕸️ Graph Structure (FalkorDB)")

    # Pyvis Graph Generation Helper
    def render_graph_view():
        try:
            from pyvis.network import Network
            net = Network(height="400px", width="100%", bgcolor="#111111", font_color="white")
            net.force_atlas_2based()

            # Query sample nodes from graph
            cypher = """
            MATCH (n)
            RETURN labels(n)[0] AS type,
                   coalesce(n.name, n.id, n.title) AS label,
                   n.id AS id
            LIMIT 30
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
            }

            for node in nodes:
                ntype = node.get("type", "Unknown")
                color = colors.get(ntype, "#FFFFFF")
                net.add_node(node["id"], label=f"{ntype}: {node['label']}", color=color)

            # Query sample edges
            edge_cypher = """
            MATCH (a)-[r]->(b)
            RETURN a.id AS from_id, b.id AS to_id, type(r) AS rel
            LIMIT 40
            """
            edges = query_graph(edge_cypher)
            for edge in edges:
                if edge["from_id"] and edge["to_id"]:
                    net.add_edge(edge["from_id"], edge["to_id"], title=edge["rel"], label=edge["rel"])

            html_data = net.generate_html()
            components.html(html_data, height=420)
        except Exception as e:
            st.warning(f"Graph visualizer standby: {e}")

    render_graph_view()
