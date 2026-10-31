"""Tests for the mocked technical-skills extraction tool."""

from candidate_skill_agent.server.tools.technical_skill_extraction import (
    extract_technical_skills,
)


async def test_extract_technical_skills_returns_expected_shape():
    # Act
    result = await extract_technical_skills("resume.pdf")

    # Assert
    assert set(result) == {"languages", "frameworks", "infrastructure"}
