"""Mocked MCP tool for document extraction: Soft Skills.

Mirrors candidate-match-agent's current mocked extraction tool: the payload is fake
until the real extraction logic lands.
"""

import asyncio
from typing import Annotated, Any

from labs_agent_lib import get_logger
from pydantic import Field

from ..mcp_server import mcp
from .types import DocumentTypeLiteral

logger = get_logger(__name__)


@mcp.tool()
async def extract_soft_skills(
    content: Annotated[
        str,
        Field(
            description=(
                "Full structured text of the document (resume or job posting) "
                "from which leadership, communication, and interpersonal soft "
                "skills will be extracted."
            )
        ),
    ],
    documentType: Annotated[
        DocumentTypeLiteral,
        Field(
            description=(
                "Type of source document being analyzed: 'resume' for candidate "
                "profiles or 'job_posting' for job descriptions."
            )
        ),
    ] = "resume",
) -> dict[str, Any]:
    """Extracts leadership, communication, and interpersonal soft skills from a resume or job posting.

    Analyzes the provided document text to identify soft skills, as either the
    candidate's demonstrated competencies (when `documentType` is `'resume'`) or
    the desired competencies for the role (when `documentType` is `'job_posting'`).

    Args:
        content: The full structured text content of the resume or job posting.
        documentType: Identifier of the document source (`"resume"` or `"job_posting"`).

    Returns:
        dict[str, Any]: A dictionary containing a `"soft_skills"` list of skill
        names (str).
    """
    logger.info(
        "Running extract_soft_skills | documentType=%s | content_length=%d",
        documentType,
        len(content),
    )
    await asyncio.sleep(0.3)

    return {
        "soft_skills": [
            "Technical Leadership",
            "Cross-functional Collaboration",
            "Mentoring",
            "Problem Solving",
        ]
    }
