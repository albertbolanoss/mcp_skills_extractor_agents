"""Resume-extraction MCP tools: mocked skill extraction."""

from .extraction_mocks import (
    extract_certifications,
    extract_languages,
    extract_soft_skills,
    extract_technical_skills,
)

EXTRACTION_TOOL_NAMES = (
    "extract_technical_skills",
    "extract_soft_skills",
    "extract_certifications",
    "extract_languages",
)

__all__ = [
    "EXTRACTION_TOOL_NAMES",
    "extract_certifications",
    "extract_languages",
    "extract_soft_skills",
    "extract_technical_skills",
]
