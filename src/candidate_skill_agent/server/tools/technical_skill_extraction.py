"""Mocked MCP tool for resume extraction: Technical Skills.

Mirrors candidate-match-agent's current mocked extraction tool: the payload is fake
until the real extraction logic lands.
"""

import asyncio

from labs_agent_lib import get_logger

from ..mcp_server import mcp

logger = get_logger(__name__)


@mcp.tool()
async def extract_technical_skills(resume_path: str) -> dict:
    """
    Extracts technical skills, programming languages, frameworks, and cloud tools from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_technical_skills for %s", resume_path)
    await asyncio.sleep(0.4)

    return {
        "languages": ["Python 3.12", "Java 21", "SQL"],
        "frameworks": ["Spring Boot 3.5", "FastMCP", "Pydantic V2"],
        "infrastructure": ["GKE Autopilot", "Apache Kafka", "Redis", "Docker"],
    }
