"""Tests for the mocked resume-extraction tools."""

import pytest

from candidate_skill_agent.server.tools.extraction_mocks import (
    _FAILED_ONCE_TRACKER,
    extract_certifications,
    extract_languages,
    extract_soft_skills,
    extract_technical_skills,
)


@pytest.fixture(autouse=True)
def clear_failure_tracker():
    """Reset the once-only failure tracker so tests don't leak state into each other."""
    _FAILED_ONCE_TRACKER.clear()
    yield
    _FAILED_ONCE_TRACKER.clear()


async def test_extract_technical_skills_returns_expected_shape():
    # Act
    result = await extract_technical_skills("resume.pdf")

    # Assert
    assert set(result) == {"languages", "frameworks", "infrastructure"}


async def test_extract_soft_skills_returns_expected_shape():
    # Act
    result = await extract_soft_skills("resume.pdf")

    # Assert
    assert "soft_skills" in result


async def test_extract_certifications_returns_expected_shape():
    # Act
    result = await extract_certifications("resume.pdf")

    # Assert
    assert "certifications" in result


async def test_extract_languages_returns_expected_shape():
    # Act
    result = await extract_languages("resume.pdf")

    # Assert
    assert "languages" in result


async def test_simulated_failure_raises_once_then_succeeds(monkeypatch):
    # Arrange
    monkeypatch.setenv("MOCK_FAIL_ONCE_FIELDS", "technical_skills")

    # Act / Assert: first call fails
    with pytest.raises(RuntimeError):
        await extract_technical_skills("resume.pdf")

    # Act / Assert: second call succeeds, the failure only triggers once
    result = await extract_technical_skills("resume.pdf")
    assert "languages" in result
