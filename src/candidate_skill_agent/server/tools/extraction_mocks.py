"""Mocked MCP tools for parallel resume extraction (Tech Skills, Soft Skills, Certifications, Languages).

These mirror candidate-match-agent's current mocked extraction tools: the payloads are fake
until the real extraction logic lands. Set env var MOCK_FAIL_ONCE_FIELDS="certifications,languages"
to simulate a crash on the first call for the listed fields.
"""

import asyncio
import os

from labs_agent_lib import get_logger

from ..mcp_server import mcp

logger = get_logger(__name__)

_FAILED_ONCE_TRACKER: set[str] = set()


def _should_simulate_failure(field_name: str) -> bool:
    """Return True on the first call if `field_name` is configured to fail once."""
    raw_targets = os.getenv("MOCK_FAIL_ONCE_FIELDS", "")
    targets = {t.strip() for t in raw_targets.split(",") if t.strip()}
    if field_name in targets and field_name not in _FAILED_ONCE_TRACKER:
        _FAILED_ONCE_TRACKER.add(field_name)
        return True
    return False


@mcp.tool()
async def extract_technical_skills(resume_path: str) -> dict:
    """
    Extracts technical skills, programming languages, frameworks, and cloud tools from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_technical_skills for %s", resume_path)
    await asyncio.sleep(0.4)

    if _should_simulate_failure("technical_skills"):
        raise RuntimeError("Simulated MCP timeout in tech-skills-agent")

    return {
        "languages": ["Python 3.12", "Java 21", "SQL"],
        "frameworks": ["Spring Boot 3.5", "FastMCP", "Pydantic V2"],
        "infrastructure": ["GKE Autopilot", "Apache Kafka", "Redis", "Docker"],
    }


@mcp.tool()
async def extract_soft_skills(resume_path: str) -> dict:
    """
    Extracts leadership, communication, and interpersonal soft skills from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_soft_skills for %s", resume_path)
    await asyncio.sleep(0.3)

    if _should_simulate_failure("soft_skills"):
        raise RuntimeError("Simulated MCP error in soft-skills-agent")

    return {
        "soft_skills": [
            "Technical Leadership",
            "Cross-functional Collaboration",
            "Mentoring",
            "Problem Solving",
        ]
    }


@mcp.tool()
async def extract_certifications(resume_path: str) -> dict:
    """
    Extracts professional certifications and credentials from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_certifications for %s", resume_path)
    await asyncio.sleep(0.5)

    if _should_simulate_failure("certifications"):
        raise RuntimeError("Simulated MCP connection drop in certs-agent")

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


@mcp.tool()
async def extract_languages(resume_path: str) -> dict:
    """
    Extracts spoken/written human languages and proficiency levels from the resume.
    Args:
        resume_path: Path of the resume being processed.
    """
    logger.info("Running extract_languages for %s", resume_path)
    await asyncio.sleep(0.2)

    if _should_simulate_failure("languages"):
        raise RuntimeError("Simulated MCP crash in lang-agent")

    return {
        "languages": [
            {"language": "Spanish", "proficiency": "Native"},
            {"language": "English", "proficiency": "B2 - Upper Intermediate"},
        ]
    }
