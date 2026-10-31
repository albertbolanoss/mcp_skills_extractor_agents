"""Mocked MCP tool for resume extraction: Soft Skills.

Mirrors candidate-match-agent's current mocked extraction tool: the payload is fake
until the real extraction logic lands.
"""

import asyncio

from labs_agent_lib import get_logger

from ..mcp_server import mcp

logger = get_logger(__name__)


@mcp.tool()
async def extract_soft_skills(resume_path: str) -> dict:
    """
    Extracts leadership, communication, and interpersonal soft skills from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_soft_skills for %s", resume_path)
    await asyncio.sleep(0.3)

    return {
        "soft_skills": [
            "Technical Leadership",
            "Cross-functional Collaboration",
            "Mentoring",
            "Problem Solving",
        ]
    }
