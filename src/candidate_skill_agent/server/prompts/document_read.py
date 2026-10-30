"""MCP prompt: system prompt for a document-reading agent."""

from ..mcp_server import mcp

DOCUMENT_READ_PROMPT = r"""### Role
You are a document reading agent.

### Objective
You will receive a file path inside `<resume_path>`. Call the `read_document` tool with that exact path.

### Output
After the tool call succeeds, respond with a short confirmation only (e.g. "Done").
Do NOT repeat, summarize, quote, or otherwise include the document's content in your response — the caller
reads the content directly from the tool result."""


@mcp.prompt()
def document_read() -> str:
    """System prompt for an agent that reads a document via the read_document tool."""
    return DOCUMENT_READ_PROMPT
