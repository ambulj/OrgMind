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
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

import litellm
from orgmind.tools import TOOLS_REGISTRY


SYSTEM_PROMPT = """You are OrgMind, the Company Brain AI assistant for Northwind Labs.
You have direct access to the Northwind Labs knowledge graph via tools.

CRITICAL OPERATIONAL RULES:
1. ONLY answer questions using facts returned directly by your tools. Never assume or invent facts.
2. CITATION MANDATE: Every single fact or decision you mention MUST cite its Source ID in brackets, like [Source: SRC_DOC_AUTH_01].
3. DECISION TRACING: If a decision was superseded, always mention both the current decision AND the older decision it replaced, citing both sources.
4. HONEST BOUNDARIES: If the tool output does not contain the answer, or returns empty results, you MUST explicitly state: "I couldn't find this in the company graph."
5. ACTIONS ARE SIMULATED: When asked to create tickets or draft messages, confirm that the action has been recorded in the graph with its simulated ID.
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
                    "tool_calls": []
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
                        return {
                            "answer": final_res.choices[0].message.content or "Completed tool investigation.",
                            "sources_used": sources_collected,
                            "tool_calls": tool_calls_executed
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
                return {
                    "answer": msg.content or "No response generated.",
                    "sources_used": sources_collected,
                    "tool_calls": tool_calls_executed
                }

        # If loop limit reached, ask model once more without tools to synthesize final answer
        try:
            final_res = litellm.completion(
                model=self.model,
                messages=messages,
                temperature=0.0,
            )
            return {
                "answer": final_res.choices[0].message.content or "Completed tool investigation.",
                "sources_used": sources_collected,
                "tool_calls": tool_calls_executed
            }
        except Exception:
            return {
                "answer": "Completed tool investigation.",
                "sources_used": sources_collected,
                "tool_calls": tool_calls_executed
            }

    def _collect_sources(self, tool_result: Any, sources_list: List[Dict[str, Any]]) -> None:
        """Helper to recursively scan tool results for Source IDs and snippets."""
        if isinstance(tool_result, dict):
            if "source_id" in tool_result and tool_result["source_id"]:
                sources_list.append(tool_result)
            for v in tool_result.values():
                self._collect_sources(v, sources_list)
        elif isinstance(tool_result, list):
            for item in tool_result:
                self._collect_sources(item, sources_list)
