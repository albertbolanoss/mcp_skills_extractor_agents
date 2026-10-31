"""Tests for the mocked soft-skills extraction tool."""

from candidate_skill_agent.server.tools.soft_skill_extraction import extract_soft_skills


async def test_extract_soft_skills_returns_expected_shape():
    # Act
    result = await extract_soft_skills("resume.pdf")

    # Assert
    assert "soft_skills" in result
