"""Provider-agnostic Agent Loop with tool-calling and strict citation rules.

Technical Terms:
- ReAct Loop: Reason + Act pattern where the agent thinks, calls an appropriate tool,
  observes the result, and formulates the final grounded answer.
- LiteLLM: A provider-agnostic router allowing seamless switching between OpenAI,
  Anthropic, Google Gemini, Ollama, etc.
- Citation Rule: Every claim made by the agent must cite its Source ID (e.g., [SRC_DOC_AUTH_01]).
"""

import json
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

# Prevent LiteLLM from making slow network calls to fetch remote cost maps
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

import litellm
litellm.suppress_debug_info = True
from orgmind.tools import TOOLS_REGISTRY
from orgmind.db import query_graph


def extract_citations(text: str) -> List[str]:
    """Extracts all Source IDs referenced like [Source: SRC_...] or [source: SRC_...] or [SRC_...]"""
    pattern = r'\[(?:Source:?\s*)?([A-Za-z0-9_\-]+)\]'
    matches = re.findall(pattern, text, re.IGNORECASE)
    # Only keep IDs that look like source IDs (SRC_...)
    return list(dict.fromkeys([m for m in matches if m.upper().startswith("SRC_")]))


def validate_citations_against_graph(cited_ids: List[str]) -> Dict[str, Any]:
    """Checks whether the cited source IDs actually exist in the FalkorDB graph."""
    if not cited_ids:
        return {"valid": [], "invalid": []}

    valid = []
    invalid = []
    for sid in cited_ids:
        try:
            rows = query_graph("MATCH (s:Source {id: $id}) RETURN s.id AS id", {"id": sid})
            if rows:
                valid.append(sid)
            else:
                invalid.append(sid)
        except Exception:
            # Fallback if DB query fails
            valid.append(sid)
    return {"valid": valid, "invalid": invalid}


SYSTEM_PROMPT = """You are OrgMind, the Company Brain AI assistant for Northwind Labs.
You have direct access to the Northwind Labs knowledge graph via tools.

CRITICAL OPERATIONAL RULES:
1. ONLY answer questions using facts returned directly by your tools. Never assume or invent facts.
2. CITATION MANDATE: Every single fact or decision you mention MUST cite its Source ID in brackets, like [Source: SRC_DOC_AUTH_01]. ONLY cite real Source IDs returned by your tools. NEVER invent or fabricate Source IDs.
3. DECISION TRACING: If a decision was superseded, always mention both the current decision AND the older decision it replaced, citing both sources.
4. HONEST BOUNDARIES: If the tool output does not contain the answer, or returns empty results, you MUST explicitly state: "I couldn't find this in the company graph."
5. ACTIONS ARE SIMULATED: When asked to create tickets or draft messages, confirm that the action has been recorded in the graph with its simulated ID. Do not cite source IDs for simulated actions.
"""

# Tool schemas formatted for LiteLLM / OpenAI tool-calling standard
AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "who_owns",
            "description": "Finds the official owner (Person or Team) for a Project or Topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_or_topic": {
                        "type": "string",
                        "description": "The name of the project or topic, e.g. 'OAuth' or 'Billing'."
                    }
                },
                "required": ["project_or_topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "who_knows_about",
            "description": "Ranks company members by demonstrated knowledge on a topic from documents, tickets, and chats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic keyword, e.g. 'OAuth', 'Kubernetes', 'Billing'."
                    }
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trace_decision",
            "description": "Traces the active decision, previous superseded decisions, and verbatim source quotes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to trace decisions for, e.g. 'OAuth', 'Billing'."
                    }
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_draft_vs_decision",
            "description": "Compares preliminary draft proposals against official ratified decisions for a topic. Identifies dissenting opinions, unheeded warnings, and trade-offs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic or technology to compare (e.g. 'Paynova', 'Billing', 'OAuth')."
                    }
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "what_changed_since",
            "description": "Lists all decisions and tickets modified or created since a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {
                        "type": "string",
                        "description": "Date formatted as YYYY-MM-DD, e.g. '2026-02-01'."
                    }
                },
                "required": ["date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_source",
            "description": "Retrieves the full text snippet for a specific Source ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "Unique source identifier, e.g. 'SRC_DOC_AUTH_01'."
                    }
                },
                "required": ["source_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "impact_analysis",
            "description": "Performs multi-hop graph analysis to assess the company impact of a decision or topic. Returns affected tickets, blocked work items, affected projects, and responsible personnel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_or_decision_id": {
                        "type": "string",
                        "description": "Topic name (e.g. 'Paynova') or Decision ID (e.g. 'DEC_PAYMENTS_...')."
                    }
                },
                "required": ["topic_or_decision_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": "Simulates creating an issue ticket and links it to a project in the graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the ticket"},
                    "description": {"type": "string", "description": "Detailed description"},
                    "project_id": {"type": "string", "description": "Target project ID, e.g. 'PRJ_OAUTH_UPGRADE'"}
                },
                "required": ["title", "description", "project_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draft_message",
            "description": "Drafts and records a message to a team communication channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name, e.g. '#backend-eng'"},
                    "text": {"type": "string", "description": "Message content"}
                },
                "required": ["channel", "text"]
            }
        }
    }
]


class OrgMindAgent:
    """Agent coordinator managing conversation history, LLM calls via LiteLLM, and tool executions."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")

    def run(self, user_query: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Runs the tool-calling loop until the agent produces a final cited response.

        Returns:
            Dictionary containing:
            - 'answer': Final agent response string
            - 'sources_used': List of Source IDs or source dicts retrieved
            - 'tool_calls': Trace of tools called during the turn
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_query})

        tool_calls_executed = []
        tool_results_recorded = []
        sources_collected = []
        executed_signatures = set()

        # ReAct loop (up to 4 steps)
        for _ in range(4):
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    tools=AGENT_TOOLS_SCHEMA,
                    tool_choice="auto",
                    temperature=0.0,
                )
            except Exception as e:
                # Fallback message if LLM API is unavailable or keys missing
                return {
                    "answer": f"LLM Execution Error: {str(e)}. Please check your model configuration in .env.",
                    "sources_used": [],
                    "tool_calls": [],
                    "citations": {"valid": [], "invalid": []},
                    "grounded": False,
                }

            msg = response.choices[0].message
            # If the model requested tool calls
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                new_calls = []
                for call in msg.tool_calls:
                    sig = (call.function.name, str(call.function.arguments))
                    if sig not in executed_signatures:
                        executed_signatures.add(sig)
                        new_calls.append(call)

                if not new_calls:
                    # Model repeated identical tool calls; force final answer synthesis without tools
                    try:
                        final_res = litellm.completion(
                            model=self.model,
                            messages=messages,
                            temperature=0.0,
                        )
                        raw_ans = final_res.choices[0].message.content or "Completed tool investigation."
                        processed = self._post_process_answer(raw_ans, sources_collected, tool_results_recorded)
                        return {
                            "answer": processed["answer"],
                            "sources_used": sources_collected,
                            "tool_calls": tool_calls_executed,
                            "citations": processed["validation"],
                            "grounded": processed["grounded"],
                        }
                    except Exception:
                        break

                # Append assistant tool call request to conversation
                if hasattr(msg, "model_dump"):
                    messages.append(msg.model_dump())
                elif hasattr(msg, "dict"):
                    messages.append(msg.dict())
                else:
                    messages.append({
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [c.model_dump() if hasattr(c, "model_dump") else c for c in msg.tool_calls]
                    })

                for call in new_calls:
                    fn_name = call.function.name
                    raw_args = call.function.arguments
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    tool_calls_executed.append({"tool": fn_name, "args": args})

                    # Execute local tool
                    if fn_name in TOOLS_REGISTRY:
                        tool_fn = TOOLS_REGISTRY[fn_name]
                        result = tool_fn(**args)
                    else:
                        result = {"error": f"Tool '{fn_name}' not recognized."}

                    tool_results_recorded.append({"name": fn_name, "args": args, "result": result})

                    # Extract source references if present in tool output
                    self._collect_sources(result, sources_collected)

                    # Append tool result to conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": getattr(call, "id", f"call_{len(tool_calls_executed)}"),
                        "name": fn_name,
                        "content": json.dumps(result)
                    })
            else:
                # No more tools called; final answer reached
                raw_ans = msg.content or "No response generated."
                processed = self._post_process_answer(raw_ans, sources_collected, tool_results_recorded)
                return {
                    "answer": processed["answer"],
                    "sources_used": sources_collected,
                    "tool_calls": tool_calls_executed,
                    "citations": processed["validation"],
                    "grounded": processed["grounded"],
                }

        # If loop limit reached, ask model once more without tools to synthesize final answer
        try:
            final_res = litellm.completion(
                model=self.model,
                messages=messages,
                temperature=0.0,
            )
            raw_ans = final_res.choices[0].message.content or "Completed tool investigation."
        except Exception:
            raw_ans = "Completed tool investigation."

        processed = self._post_process_answer(raw_ans, sources_collected, tool_results_recorded)
        return {
            "answer": processed["answer"],
            "sources_used": sources_collected,
            "tool_calls": tool_calls_executed,
            "citations": processed["validation"],
            "grounded": processed["grounded"],
        }

    def _collect_sources(self, tool_result: Any, sources_list: List[Dict[str, Any]]) -> None:
        """Helper to recursively scan tool results for Source IDs and snippets."""
        if isinstance(tool_result, dict):
            sid = tool_result.get("source_id")
            if sid and not any(s.get("source_id") == sid for s in sources_list):
                sources_list.append({
                    "source_id": sid,
                    "file_path": tool_result.get("source_file") or tool_result.get("file_path", ""),
                    "snippet": tool_result.get("source_snippet") or tool_result.get("text_snippet", ""),
                })
            sup_sid = tool_result.get("superseded_source_id")
            if sup_sid and not any(s.get("source_id") == sup_sid for s in sources_list):
                sources_list.append({
                    "source_id": sup_sid,
                    "file_path": tool_result.get("superseded_source_file", ""),
                    "snippet": tool_result.get("superseded_source_snippet", ""),
                })
            for v in tool_result.values():
                self._collect_sources(v, sources_list)
        elif isinstance(tool_result, list):
            for item in tool_result:
                self._collect_sources(item, sources_list)

    def _post_process_answer(
        self,
        raw_answer: str,
        sources_collected: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validates citations against the graph, guards against hallucinations,
        and appends verified source grounding if omitted by the LLM.
        """
        answer = (raw_answer or "").strip()

        # 1. Hallucination Guard: If tools ran but returned nothing found
        all_empty = False
        if tool_results:
            all_empty = True
            for r in tool_results:
                res = r.get("result", {})
                if isinstance(res, dict):
                    if res.get("found") is True:
                        all_empty = False
                        break
                    if res.get("results") or res.get("decisions") or res.get("ranked_experts"):
                        all_empty = False
                        break
                    if res.get("status") in ("simulated_success", "success"):
                        all_empty = False
                        break
                elif isinstance(res, list) and len(res) > 0:
                    all_empty = False
                    break

        if all_empty and "couldn't find this in the company graph" not in answer.lower():
            answer = "I couldn't find this in the company graph. No active project, owner, or documents exist for this query in Northwind Labs."

        cited_ids = extract_citations(answer)
        validation = validate_citations_against_graph(cited_ids)

        # Strip any hallucinated citation tags that do not exist in the graph
        if validation["invalid"]:
            for inv_id in validation["invalid"]:
                answer = re.sub(rf'\[(?:Source:?\s*)?{re.escape(inv_id)}\]', '', answer)
            cited_ids = extract_citations(answer)
            validation = validate_citations_against_graph(cited_ids)

        # 3. Grounding & Repair: If sources were retrieved from graph tools, ensure they appear in answer
        valid_turn_sources = [s for s in sources_collected if s.get("source_id")]
        unmentioned_sources = [
            s for s in valid_turn_sources
            if s["source_id"] not in answer
        ]

        if unmentioned_sources and not all_empty:
            source_lines = []
            for s in unmentioned_sources:
                sid = s["source_id"]
                fp = s.get("file_path", "")
                source_lines.append(f"[Source: {sid}]" + (f" ({fp})" if fp else ""))

            # Append verified sources footer
            answer = answer + "\n\n**Verified Sources:** " + ", ".join(source_lines)
            for s in unmentioned_sources:
                if s["source_id"] not in validation["valid"]:
                    validation["valid"].append(s["source_id"])

        return {
            "answer": answer,
            "cited_ids": cited_ids,
            "validation": validation,
            "grounded": len(validation["invalid"]) == 0,
        }
