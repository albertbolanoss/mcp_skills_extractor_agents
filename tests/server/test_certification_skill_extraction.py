"""Tests for the mocked certifications extraction tool."""

from candidate_skill_agent.server.tools.certification_skill_extraction import (
    extract_certifications,
)


async def test_extract_certifications_returns_expected_shape():
    # Act
    result = await extract_certifications("resume.pdf")

    # Assert
    assert "certifications" in result
