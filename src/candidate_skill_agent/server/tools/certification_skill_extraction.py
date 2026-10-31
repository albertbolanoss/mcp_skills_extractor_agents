"""Mocked MCP tool for document extraction: Certifications.

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
async def extract_certifications(
    content: Annotated[
        str,
        Field(
            description=(
                "Full structured text of the document (resume or job posting) "
                "from which professional certifications and credentials will be "
                "extracted."
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
    """Extracts professional certifications and credentials from a resume or job posting.

    Analyzes the provided document text to identify certifications, as either
    the candidate's held credentials (when `documentType` is `'resume'`) or the
    required/preferred certifications for the role (when `documentType` is
    `'job_posting'`).

    Args:
        content: The full structured text content of the resume or job posting.
        documentType: Identifier of the document source (`"resume"` or `"job_posting"`).

    Returns:
        dict[str, Any]: A dictionary containing a `"certifications"` list, where
        each item maps `"name"`, `"issuer"`, and `"status"` (str).
    """
    logger.info(
        "Running extract_certifications | documentType=%s | content_length=%d",
        documentType,
        len(content),
    )
    await asyncio.sleep(0.5)

    return {
        "certifications": [
            {
                "name": "Claude Certified Architect - Foundations",
                "issuer": "Anthropic",
                "status": "Active",
            },
            {
                "name": "SnowPro Core Certification",
                "issuer": "Snowflake",
                "status": "Active",
            },
        ]
    }
