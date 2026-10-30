"""Resume-extraction MCP tools: document reading + mocked skill extraction."""

from .extraction_mocks import (
    extract_certifications,
    extract_languages,
    extract_soft_skills,
    extract_technical_skills,
)
from .file_reader import read_document

READ_DOCUMENT_TOOL_NAME = "read_document"
EXTRACTION_TOOL_NAMES = (
    "extract_technical_skills",
    "extract_soft_skills",
    "extract_certifications",
    "extract_languages",
)

__all__ = [
    "EXTRACTION_TOOL_NAMES",
    "READ_DOCUMENT_TOOL_NAME",
    "extract_certifications",
    "extract_languages",
    "extract_soft_skills",
    "extract_technical_skills",
    "read_document",
]
