"""Mocked MCP tool for document extraction: Technical Skills.

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
async def extract_technical_skills(
    content: Annotated[
        str,
        Field(
            description=(
                "Full structured text of the document (resume or job posting) "
                "from which technical skills will be extracted."
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
    """Extracts programming languages, frameworks, and infrastructure tools from a resume or job posting.

    Analyzes the provided document text to identify technical skills such as
    programming languages, frameworks, and cloud/infrastructure tools, as either
    the candidate's demonstrated expertise (when `documentType` is `'resume'`) or
    the required/preferred stack for the role (when `documentType` is
    `'job_posting'`).

    Args:
        content: The full structured text content of the resume or job posting.
        documentType: Identifier of the document source (`"resume"` or `"job_posting"`).

    Returns:
        dict[str, Any]: A dictionary with `"languages"`, `"frameworks"`, and
        `"infrastructure"` keys, each mapping to a list of skill names (str).
    """
    logger.info(
        "Running extract_technical_skills | documentType=%s | content_length=%d",
        documentType,
        len(content),
    )
    await asyncio.sleep(0.4)

    return {
        "languages": ["Python 3.12", "Java 21", "SQL"],
        "frameworks": ["Spring Boot 3.5", "FastMCP", "Pydantic V2"],
        "infrastructure": ["GKE Autopilot", "Apache Kafka", "Redis", "Docker"],
    }
