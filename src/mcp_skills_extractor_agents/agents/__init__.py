"""Claude-agent-backed extraction pipelines, decoupled from their MCP tool wrappers.

Each subpackage (e.g. `technical_skills`) owns its own agent definitions, prompts,
Pydantic schemas and orchestration, independent of the thin `@mcp.tool()` wrapper
under `server/tools/` that invokes it.
"""
