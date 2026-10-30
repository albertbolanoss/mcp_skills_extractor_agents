"""MCP tool for extracting text from a document (resume, job posting, etc)."""

from labs_agent_lib.file_reader import extract_text

from ..mcp_server import mcp


@mcp.tool()
def read_document(file_path: str) -> str:
    """
    Extract the text content of a document (resume, job posting, etc).
    Supported extensions: .docx, .markdown, .md, .pdf, .txt.
    Args:
        file_path: Path to the document to read.
    """
    return extract_text(file_path)
