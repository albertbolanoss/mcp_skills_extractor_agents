"""Agent-specific extraction pipelines, decoupled from the MCP tool layer.

Each subpackage owns one skill-extraction domain's prompts, Pydantic schemas, Claude
Agent SDK agent definitions and orchestration logic. The `server/tools/` modules stay
thin `@mcp.tool()` entrypoints that delegate to these pipelines.
"""
