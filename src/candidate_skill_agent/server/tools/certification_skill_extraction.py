"""Mocked MCP tool for resume extraction: Certifications.

Mirrors candidate-match-agent's current mocked extraction tool: the payload is fake
until the real extraction logic lands.
"""

import asyncio

from labs_agent_lib import get_logger

from ..mcp_server import mcp

logger = get_logger(__name__)


@mcp.tool()
async def extract_certifications(resume_path: str) -> dict:
    """
    Extracts professional certifications and credentials from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_certifications for %s", resume_path)
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
