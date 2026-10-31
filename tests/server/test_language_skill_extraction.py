"""Tests for the mocked languages extraction tool."""

from candidate_skill_agent.server.tools.language_skill_extraction import (
    extract_languages,
)


async def test_extract_languages_returns_expected_shape():
    # Act
    result = await extract_languages("resume.pdf")

    # Assert
    assert "languages" in result
