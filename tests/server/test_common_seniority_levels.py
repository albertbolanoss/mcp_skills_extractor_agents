"""Tests for the common-seniority-levels MCP resource."""

from mcp_skills_extractor_agents.server.resources.common_seniority_levels import (
    COMMON_SENIORITY_LEVELS,
    common_seniority_levels,
    normalize_seniority_level,
)


def test_common_seniority_levels_has_multiple_levels():
    # Act
    levels = common_seniority_levels()

    # Assert
    assert levels is COMMON_SENIORITY_LEVELS
    assert len(levels) > 5
    assert {"Junior", "Mid-Level", "Senior"} <= levels.keys()


def test_normalize_seniority_level_resolves_known_alias():
    # Act / Assert
    assert normalize_seniority_level("Sr") == "Senior"
    assert normalize_seniority_level("Middle") == "Mid-Level"
    assert normalize_seniority_level("Tech Lead") == "Lead"


def test_normalize_seniority_level_is_case_insensitive_on_canonical_name():
    # Act / Assert
    assert normalize_seniority_level("junior") == "Junior"
    assert normalize_seniority_level("JUNIOR") == "Junior"


def test_normalize_seniority_level_returns_none_for_unknown_level():
    # Act / Assert
    assert normalize_seniority_level("some-made-up-level") is None
