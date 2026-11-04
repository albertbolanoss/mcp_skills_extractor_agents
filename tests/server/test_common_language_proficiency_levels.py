"""Tests for the common-language-proficiency-levels MCP resource."""

from mcp_skills_extractor_agents.server.resources.common_language_proficiency_levels import (
    COMMON_LANGUAGE_PROFICIENCY_LEVELS,
    common_language_proficiency_levels,
    normalize_language_proficiency,
)


def test_common_language_proficiency_levels_covers_full_cefr_scale():
    # Act
    levels = common_language_proficiency_levels()

    # Assert
    assert levels is COMMON_LANGUAGE_PROFICIENCY_LEVELS
    assert set(levels.keys()) == {"A1", "A2", "B1", "B2", "C1", "C2"}


def test_normalize_language_proficiency_resolves_known_alias():
    # Act / Assert
    assert normalize_language_proficiency("Fluent") == "C2"
    assert normalize_language_proficiency("Upper Intermediate") == "B2"
    assert normalize_language_proficiency("  Native ") == "C2"


def test_normalize_language_proficiency_is_case_insensitive_on_canonical_name():
    # Act / Assert
    assert normalize_language_proficiency("b2") == "B2"
    assert normalize_language_proficiency("B2") == "B2"


def test_normalize_language_proficiency_returns_none_for_unknown_level():
    # Act / Assert
    assert normalize_language_proficiency("some-made-up-level") is None
