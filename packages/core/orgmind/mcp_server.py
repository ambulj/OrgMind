"""Custom OrgMind MCP Server (Python).

Technical Terms:
- MCP (Model Context Protocol): Standard protocol allowing LLMs and AI apps to discover
  and call tools, read resources, and access prompts over stdio or SSE.
- FastMCP: A high-level Python framework for building MCP servers with minimal boilerplate.
"""

import json

try:
    from mcp.server import MCPServer as FastMCP
except Exception:
    from mcp.server.fastmcp import FastMCP  # type: ignore[attr-defined,no-redef]
from orgmind.freshness import impact_analysis as tool_impact_analysis
from orgmind.tools import (
    assign_task as tool_assign_task,
)
from orgmind.tools import (
    compare_draft_vs_decision as tool_compare_draft_vs_decision,
)
from orgmind.tools import (
    create_ticket as tool_create_ticket,
)
from orgmind.tools import (
    draft_message as tool_draft_message,
)
from orgmind.tools import (
    find_related as tool_find_related,
)
from orgmind.tools import (
    get_source as tool_get_source,
)
from orgmind.tools import (
    trace_decision as tool_trace_decision,
)
from orgmind.tools import (
    what_changed_since as tool_what_changed_since,
)
from orgmind.tools import (
    who_knows_about as tool_who_knows_about,
)
from orgmind.tools import (
    who_owns as tool_who_owns,
)

# Initialize FastMCP Server
mcp = FastMCP("OrgMind-Company-Brain")


@mcp.tool()
def who_owns(project_or_topic: str) -> str:
    """Finds who owns a project or topic in Northwind Labs.

    Args:
        project_or_topic: Name of the project or topic (e.g. 'OAuth', 'Billing').
    """
    result = tool_who_owns(project_or_topic)
    return json.dumps(result, indent=2)


@mcp.tool()
def who_knows_about(topic: str) -> str:
    """Ranks company members by demonstrated knowledge on a topic using weighted graph evidence.

    Args:
        topic: Topic keyword (e.g. 'OAuth', 'Paynova', 'Kubernetes').
    """
    result = tool_who_knows_about(topic)
    return json.dumps(result, indent=2)


@mcp.tool()
def trace_decision(topic: str) -> str:
    """Traces active decisions, historical superseded decisions, and source citations for a topic.

    Args:
        topic: Topic name (e.g. 'OAuth', 'Paynova', 'Billing').
    """
    result = tool_trace_decision(topic)
    return json.dumps(result, indent=2)


@mcp.tool()
def compare_draft_vs_decision(topic: str) -> str:
    """Compares preliminary draft technical recommendations against ratified official policy.

    Args:
        topic: Topic name (e.g. 'Paynova', 'Billing').
    """
    result = tool_compare_draft_vs_decision(topic)
    return json.dumps(result, indent=2)


@mcp.tool()
def impact_analysis(target: str) -> str:
    """Performs multi-hop graph dependency analysis tracing affected projects, tickets, and blockers.

    Args:
        target: Topic name or Decision ID (e.g. 'Paynova', 'DEC_PAYMENTS_2026_03_PAYNOVA').
    """
    result = tool_impact_analysis(target)
    return json.dumps(result, indent=2)


@mcp.tool()
def what_changed_since(date_str: str) -> str:
    """Lists all changes (decisions and tickets) since a given date (YYYY-MM-DD).

    Args:
        date_str: ISO date string, e.g. '2026-02-01'.
    """
    result = tool_what_changed_since(date_str)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_source(source_id: str) -> str:
    """Fetches the exact text snippet for a Source ID to guarantee factual grounding.

    Args:
        source_id: Identifier of the source chunk, e.g. 'SRC_DOC_AUTH_01'.
    """
    result = tool_get_source(source_id)
    return json.dumps(result, indent=2)


@mcp.tool()
def find_related(entity: str, hops: int = 2) -> str:
    """Finds neighboring nodes connected up to N hops away from an entity.

    Args:
        entity: Entity name or ID.
        hops: Number of relationship hops (1-3).
    """
    result = tool_find_related(entity, hops)
    return json.dumps(result, indent=2)


@mcp.tool()
def create_ticket(title: str, description: str, project_id: str, confirm: bool = True) -> str:
    """Simulates creating an issue ticket and links it into the graph.

    Args:
        title: Title of the ticket.
        description: Description of the work.
        project_id: Target project ID.
        confirm: True to commit to graph; False to return proposal preview.
    """
    result = tool_create_ticket(title, description, project_id, confirm=confirm)
    return json.dumps(result, indent=2)


@mcp.tool()
def draft_message(channel: str, text: str, confirm: bool = True) -> str:
    """Simulates drafting a message to a team communication channel.

    Args:
        channel: Channel name, e.g. '#backend-eng'.
        text: Message draft content.
        confirm: True to commit to graph; False to return proposal preview.
    """
    result = tool_draft_message(channel, text, confirm=confirm)
    return json.dumps(result, indent=2)


@mcp.tool()
def assign_task(
    task_title: str, assignee_person_id: str, project_id: str, confirm: bool = True
) -> str:
    """Assigns a project task to a team member in the graph.

    Args:
        task_title: Title of the assigned task.
        assignee_person_id: Person ID (e.g. 'P_ALICE').
        project_id: Target Project ID.
        confirm: True to commit to graph; False to return proposal preview.
    """
    result = tool_assign_task(task_title, assignee_person_id, project_id, confirm=confirm)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    # Runs the MCP server over stdio for Claude Desktop or client connection
    mcp.run()
