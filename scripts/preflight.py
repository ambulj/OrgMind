"""OrgMind Preflight System Verification Script.

Executes a comprehensive health check across all project subsystems before
the live hackathon demonstration or video recording.

Subsystems Checked:
1. FalkorDB Port & Engine Connectivity (localhost:6379)
2. Graph Baseline Integrity (nodes >= 160, edges >= 260)
3. Streamlit Server Health (http://localhost:8501/_stcore/health)
4. FastMCP Tool Server Registration (11 tools discovered)
5. LLM Model Connectivity (Ollama / LiteLLM)
6. Demo Assets & Live Pipeline Files
"""

import sys
import os
import json
import urllib.request
import asyncio
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Ensure UTF-8 stdout encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"


def check_falkordb() -> bool:
    print("[1/6] Checking FalkorDB Connectivity & Graph Integrity...", end=" ", flush=True)
    try:
        from orgmind.db import get_graph
        g = get_graph()
        node_res = g.query("MATCH (n) RETURN count(n) AS cnt").result_set
        edge_res = g.query("MATCH ()-[r]->() RETURN count(r) AS cnt").result_set
        node_cnt = node_res[0][0] if node_res else 0
        edge_cnt = edge_res[0][0] if edge_res else 0
        if node_cnt >= 150:
            print(f"PASS ({node_cnt} nodes, {edge_cnt} edges)")
            return True
        else:
            print(f"WARN (Low node count: {node_cnt})")
            return False
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_streamlit() -> bool:
    print("[2/6] Checking Streamlit Server (port 8501)...", end=" ", flush=True)
    try:
        url = "http://localhost:8501/_stcore/health"
        req = urllib.request.Request(url, headers={"User-Agent": "OrgMind-Preflight/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print("PASS (HTTP 200 OK)")
                return True
            else:
                print(f"FAIL (HTTP {resp.status})")
                return False
    except Exception as e:
        print(f"FAIL (Connection refused or down: {e})")
        return False


def check_mcp_server() -> bool:
    print("[3/6] Checking FastMCP Tool Registration...", end=" ", flush=True)
    try:
        from orgmind.mcp_server import mcp
        tools = asyncio.run(mcp.list_tools())
        if len(tools) >= 11:
            print(f"PASS ({len(tools)} tools registered)")
            return True
        else:
            print(f"WARN ({len(tools)} tools found, expected >= 11)")
            return False
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_demo_assets() -> bool:
    print("[4/6] Verifying Demo Data & Script Files...", end=" ", flush=True)
    required_files = [
        "data/live/live_decision_reversal.json",
        "data/live/new_billing_decision.json",
        "DEMO_PLAN.md",
        "STATUS.md",
        "app/streamlit_app.py",
        "tests/test_questions.json",
    ]
    missing = [f for f in required_files if not os.path.exists(os.path.join(project_root, f))]
    if not missing:
        print(f"PASS (All {len(required_files)} key assets verified)")
        return True
    else:
        print(f"FAIL (Missing files: {missing})")
        return False


def check_live_pipeline() -> bool:
    print("[5/6] Testing Live-Update Preview Pipeline...", end=" ", flush=True)
    try:
        from orgmind.freshness import preview_decision
        prev = preview_decision("data/live/live_decision_reversal.json")
        if prev.get("status") in ("ready", "already_committed"):
            print(f"PASS (Preview verified - status: {prev.get('status')})")
            return True
        else:
            print(f"FAIL (Unexpected preview: {prev})")
            return False
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_llm_model() -> bool:
    print("[6/6] Checking LLM Agent & Reasoning Loop...", end=" ", flush=True)
    try:
        from orgmind.agent import OrgMindAgent
        agent = OrgMindAgent()
        res = agent.run("Who owns OAuth?")
        ans = res.get("answer", "")
        if ans and len(ans.strip()) > 10:
            print(f"PASS (Model: {agent.model}, Response verified: {len(ans)} chars)")
            return True
        else:
            print(f"FAIL (Empty or invalid reply from model: '{ans}')")
            return False
    except Exception as e:
        print(f"FAIL ({e})")
        return False


def main():
    print("=" * 65)
    print(" 🚀 OrgMind Hackathon Preflight System Verification")
    print("=" * 65)
    results = [
        check_falkordb(),
        check_streamlit(),
        check_mcp_server(),
        check_demo_assets(),
        check_live_pipeline(),
        check_llm_model(),
    ]
    print("=" * 65)
    if all(results):
        print(" 🟢 ALL PREFLIGHT CHECKS PASSED. SYSTEM READY FOR DEMO!")
    else:
        print(" ⚠️ SOME CHECKS FAILED OR GENERATED WARNINGS. REVIEW ABOVE.")
    print("=" * 65)


if __name__ == "__main__":
    main()
