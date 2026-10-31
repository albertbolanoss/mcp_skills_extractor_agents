"""Mocked MCP tool for document extraction: Languages.

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
async def extract_languages(
    content: Annotated[
        str,
        Field(
            description=(
                "Full structured text of the document (resume or job posting) "
                "from which spoken and written human languages will be extracted."
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
    """Extracts spoken/written human languages and proficiency levels from a resume or job posting.

    Analyzes the provided document text to identify human languages (e.g., Spanish,
    English, Portuguese) along with either the candidate's stated proficiency level
    (when `documentType` is `'resume'`) or the required/preferred proficiency level
    for the role (when `documentType` is `'job_posting'`). Do not confuse human
    languages with programming languages.

    Args:
        content: The full structured text content of the resume or job posting.
        documentType: Identifier of the document source (`"resume"` or `"job_posting"`).

    Returns:
        dict[str, Any]: A dictionary containing a `"languages"` list, where each item
        maps `"language"` (str) to `"proficiency"` (str).
    """
    logger.info(
        "Running extract_languages | documentType=%s | content_length=%d",
        documentType,
        len(content),
    )
    await asyncio.sleep(0.2)

    return {
        "languages": [
            {"language": "Spanish", "proficiency": "Native"},
            {"language": "English", "proficiency": "B2 - Upper Intermediate"},
        ]
    }
