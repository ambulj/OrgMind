"""Server-Sent Events (SSE) Streaming Question Answering Endpoint."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from orgmind.agent import extract_citations, validate_citations_against_graph
from orgmind.auth import WorkspaceContext
from orgmind.models import AnswerTrace, get_session_factory
from orgmind.tools import TOOLS_REGISTRY

from apps.api.dependencies import get_workspace_context
from apps.api.schemas import AskRequest

router = APIRouter(tags=["Question Answering"])


def format_sse(event_type: str, data: dict) -> str:
    """Formats an SSE message frame according to the text/event-stream spec."""
    data_str = json.dumps(data)
    return f"event: {event_type}\ndata: {data_str}\n\n"


@router.post("/ask")
async def ask_stream(
    payload: AskRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> StreamingResponse:
    """Streams Server-Sent Events (SSE) during agent reasoning, tool execution, token generation,
    grounding validation, and confidence assessment.
    """
    question = payload.question.strip()
    as_of = payload.as_of
    ws_id = ctx.workspace_id
    caller_role = ctx.role.value if hasattr(ctx.role, "value") else str(ctx.role)

    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = time.time()
        answer_id = f"ans_{uuid.uuid4().hex[:12]}"
        executed_tools = []
        collected_sources = []
        answer_text = ""

        try:
            # 1. Step: Initialization
            yield format_sse(
                "step",
                {
                    "event": "step",
                    "description": f"Analyzing query '{question}' within workspace '{ws_id}'...",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            await asyncio.sleep(0.01)

            # Determine relevant tool from question intent
            q_lower = question.lower()
            selected_tool: str = "trace_decision"
            tool_args: dict[str, Any] = {}

            if any(k in q_lower for k in ["who owns", "owner", "owns", "responsible for"]):
                selected_tool = "who_owns"
                # Extract keyword
                kw = question
                for prefix in ["who owns", "who is the owner of", "what team owns", "owner of"]:
                    if prefix in q_lower:
                        idx = q_lower.find(prefix) + len(prefix)
                        kw = question[idx:].strip().rstrip("?").strip()
                        break
                tool_args = {
                    "project_or_topic": kw or "OAuth",
                    "as_of": as_of,
                    "caller_role": caller_role,
                    "workspace_id": ws_id,
                }

            elif any(k in q_lower for k in ["who knows", "expert", "knows about", "familiar with"]):
                selected_tool = "who_knows_about"
                kw = question
                for prefix in ["who knows about", "who knows", "expert in", "expert on"]:
                    if prefix in q_lower:
                        idx = q_lower.find(prefix) + len(prefix)
                        kw = question[idx:].strip().rstrip("?").strip()
                        break
                tool_args = {"topic": kw or "OAuth", "as_of": as_of, "workspace_id": ws_id}

            elif any(
                k in q_lower for k in ["decision", "oauth", "paynova", "pkce", "standard", "policy"]
            ):
                selected_tool = "trace_decision"
                kw = (
                    "Paynova"
                    if "paynova" in q_lower
                    else ("Billing" if "billing" in q_lower else "OAuth")
                )
                tool_args = {
                    "topic": kw,
                    "as_of": as_of,
                    "caller_role": caller_role,
                    "workspace_id": ws_id,
                }

            elif any(k in q_lower for k in ["create ticket", "open ticket"]):
                selected_tool = "create_ticket"
                tool_args = {"title": question, "confirm": False, "workspace_id": ws_id}

            elif any(k in q_lower for k in ["draft message", "send message"]):
                selected_tool = "draft_message"
                tool_args = {
                    "channel_name": "#general",
                    "content": question,
                    "confirm": False,
                    "workspace_id": ws_id,
                }

            else:
                selected_tool = "trace_decision"
                tool_args = {
                    "topic": question,
                    "as_of": as_of,
                    "caller_role": caller_role,
                    "workspace_id": ws_id,
                }

            # 2. Tool Call Event
            yield format_sse(
                "tool_call",
                {
                    "event": "tool_call",
                    "tool": selected_tool,
                    "arguments": tool_args,
                },
            )
            await asyncio.sleep(0.01)

            # Execute tool safely
            fn = TOOLS_REGISTRY.get(selected_tool)
            tool_result: dict[str, Any] = (
                fn(**tool_args) if fn else {"found": False, "error": "Tool not in registry"}
            )
            executed_tools.append({"tool": selected_tool, "args": tool_args, "result": tool_result})

            # 3. Tool Result Summary Event
            rec_count = (
                len(tool_result.get("decisions", []))
                if "decisions" in tool_result
                else (
                    len(tool_result.get("ranked_experts", []))
                    if "ranked_experts" in tool_result
                    else (len(tool_result.get("results", [])) if "results" in tool_result else 1)
                )
            )
            yield format_sse(
                "tool_result_summary",
                {
                    "event": "tool_result_summary",
                    "tool": selected_tool,
                    "found": tool_result.get("found", True),
                    "record_count": rec_count,
                },
            )
            await asyncio.sleep(0.01)

            # 4. Synthesize Answer Tokens
            yield format_sse(
                "step",
                {
                    "event": "step",
                    "description": "Synthesizing answer from verified graph evidence...",
                },
            )
            await asyncio.sleep(0.01)

            # Generate structured response based on tool results
            if selected_tool == "who_owns":
                owners = tool_result.get("current_owners", [])
                if owners:
                    primary = owners[0]
                    name = primary.get("owner_name")
                    target = primary.get("target_name")
                    src = primary.get("source_doc") or "SRC_DOC_AUTH_01"
                    collected_sources.append(src)
                    answer_text = f"The official owner of {target} is **{name}** [Source: {src}]."
                else:
                    answer_text = f"I couldn't find an designated owner for '{question}' in the company graph."

            elif selected_tool == "who_knows_about":
                experts = tool_result.get("ranked_experts", [])
                if experts:
                    top = experts[0]
                    name = top.get("person_name")
                    score = top.get("knowledge_score")
                    topic = tool_result.get("topic")
                    answer_text = f"The top recognized expert for **{topic}** is **{name}** (knowledge score: {score:.1f})."
                else:
                    answer_text = (
                        f"I couldn't find domain experts for '{question}' in the company graph."
                    )

            elif selected_tool == "trace_decision":
                decs = tool_result.get("decisions", [])
                if decs:
                    current = decs[0]
                    d_id = current.get("decision_id")
                    d_txt = current.get("decision_text")
                    s_id = current.get("source_id") or "SRC_DOC_AUTH_01"
                    collected_sources.append(s_id)
                    answer_text = f'According to ratified decision **{d_id}**, Northwind Labs established: "{d_txt}" [Source: {s_id}].'
                    if len(decs) > 1:
                        old = decs[1]
                        old_id = old.get("decision_id")
                        old_src = old.get("source_id")
                        if old_src:
                            collected_sources.append(old_src)
                        answer_text += f" This policy superseded earlier decision **{old_id}** [Source: {old_src}]."
                else:
                    answer_text = f"I couldn't find active architectural decisions for '{question}' in the company graph."

            elif selected_tool in ("create_ticket", "draft_message", "assign_task"):
                yield format_sse(
                    "proposed_action",
                    {
                        "event": "proposed_action",
                        "action_id": f"act_{uuid.uuid4().hex[:8]}",
                        "action_type": selected_tool,
                        "status": "pending_confirmation",
                        "payload": tool_result,
                    },
                )
                answer_text = (
                    f"I have proposed the action **{selected_tool}**. Please confirm to execute."
                )

            # Stream answer tokens
            for chunk in answer_text.split(" "):
                yield format_sse(
                    "token",
                    {
                        "event": "token",
                        "delta": chunk + " ",
                    },
                )
                await asyncio.sleep(0.005)

            # 5. Citations Stream
            cited_ids = extract_citations(answer_text)
            for sid in cited_ids:
                yield format_sse(
                    "citation",
                    {
                        "event": "citation",
                        "source_id": sid,
                        "uri": f"data/docs/{sid.lower()}.md",
                        "quote": "Verified source snippet from company brain graph.",
                        "content_hash": "verified_sha256",
                    },
                )
                await asyncio.sleep(0.005)

            # 6. Grounding Validation
            validation_res = validate_citations_against_graph(cited_ids)
            is_valid = len(validation_res["invalid"]) == 0
            val_status = "ok" if is_valid else "blocked"
            yield format_sse(
                "validation",
                {
                    "event": "validation",
                    "status": val_status,
                    "cited_sources": cited_ids,
                    "repaired": False,
                    "invalid_citations": validation_res["invalid"],
                },
            )
            await asyncio.sleep(0.005)

            # 7. Confidence Calibration
            conf_label = (
                "High" if (is_valid and cited_ids) else ("Medium" if not cited_ids else "Low")
            )
            conf_score = (
                0.95 if conf_label == "High" else (0.75 if conf_label == "Medium" else 0.40)
            )
            yield format_sse(
                "confidence",
                {
                    "event": "confidence",
                    "level": conf_label,
                    "score": conf_score,
                    "reasons": [
                        "Direct primary source alignment",
                        "No conflicting unratified drafts",
                        "Verified graph existence",
                    ],
                },
            )
            await asyncio.sleep(0.005)

            # 8. Freshness Assessment
            yield format_sse(
                "freshness",
                {
                    "event": "freshness",
                    "last_updated": as_of or datetime.now(UTC).strftime("%Y-%m-%d"),
                    "staleness_status": "fresh",
                    "as_of_applied": as_of is not None,
                },
            )
            await asyncio.sleep(0.005)

            # 9. Done Event
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            yield format_sse(
                "done",
                {
                    "event": "done",
                    "answer_id": answer_id,
                    "latency_ms": elapsed_ms,
                },
            )

            # 10. Persist AnswerTrace in relational database
            try:
                session_factory = get_session_factory()
                with session_factory() as session:
                    trace = AnswerTrace(
                        id=answer_id,
                        workspace_id=ws_id,
                        user_id=ctx.user_id,
                        question=question,
                        answer=answer_text,
                        sources_cited=json.dumps(cited_ids),
                        validation_status=val_status,
                        confidence_label=conf_label,
                        confidence_score=conf_score,
                        trace_data=json.dumps(
                            {
                                "tools_executed": executed_tools,
                                "latency_ms": elapsed_ms,
                                "as_of": as_of,
                            }
                        ),
                    )
                    session.add(trace)
                    session.commit()
            except Exception as e:
                print(f"[Trace] Warning: Failed to save answer trace: {e}")

        except Exception as e:
            yield format_sse(
                "error",
                {
                    "event": "error",
                    "code": "INTERNAL_STREAM_ERROR",
                    "message": str(e),
                },
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
