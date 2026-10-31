"""Mocked MCP tool for resume extraction: Languages.

Mirrors candidate-match-agent's current mocked extraction tool: the payload is fake
until the real extraction logic lands.
"""

import asyncio

from labs_agent_lib import get_logger

from ..mcp_server import mcp

logger = get_logger(__name__)


@mcp.tool()
async def extract_languages(resume_path: str) -> dict:
    """
    Extracts spoken/written human languages and proficiency levels from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_languages for %s", resume_path)
    await asyncio.sleep(0.2)

    return {
        "languages": [
            {"language": "Spanish", "proficiency": "Native"},
            {"language": "English", "proficiency": "B2 - Upper Intermediate"},
        ]
    }
