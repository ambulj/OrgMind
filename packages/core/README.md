# OrgMind Core Engine

`packages/core` provides the foundational knowledge graph layer, agent reasoning engine, entity resolution, and FalkorDB graph schema for OrgMind.

## Modules
- `orgmind.db`: FalkorDB connection pooling, schema initialization, parameterised OpenCypher queries.
- `orgmind.agent`: LiteLLM-based ReAct agent with programmatic citation validation.
- `orgmind.tools`: Role-aware agent tools with weighted expertise scoring.
- `orgmind.freshness`: Non-destructive superseding (`[:SUPERSEDES]`), 2-phase preview/commit, impact analysis.
- `orgmind.resolve`: Fuzzy alias matching and unknown entity quarantine.
- `orgmind.mcp_server`: FastMCP server exposing graph tools to external LLM clients.
