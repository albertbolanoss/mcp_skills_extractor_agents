"""MCP prompts for the resume-extraction coordinator and its sub-agents."""

from .coordinator_orchestration import (
    COORDINATOR_ORCHESTRATION_PROMPT,
    coordinator_orchestration,
)
from .document_read import DOCUMENT_READ_PROMPT, document_read

__all__ = [
    "COORDINATOR_ORCHESTRATION_PROMPT",
    "DOCUMENT_READ_PROMPT",
    "coordinator_orchestration",
    "document_read",
]
