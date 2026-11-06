"""Tests for the common-soft-skills MCP resource."""

from mcp_skills_extractor_agents.server.resources.common_soft_skills import (
    COMMON_SOFT_SKILLS,
    common_soft_skills,
    normalize_soft_skill,
)


def test_common_soft_skills_has_multiple_categories_and_skills():
    # Act
    taxonomy = common_soft_skills()

    # Assert
    assert taxonomy is COMMON_SOFT_SKILLS
    assert len(taxonomy) > 5
    assert all(len(skills) > 0 for skills in taxonomy.values())


def test_normalize_soft_skill_resolves_known_alias():
    # Act / Assert
    assert normalize_soft_skill("Team Player") == "Teamwork"
    assert normalize_soft_skill("Coaching") == "Mentoring"
    assert normalize_soft_skill("  EQ ") == "Emotional Intelligence"


def test_normalize_soft_skill_is_case_insensitive_on_canonical_name():
    # Act / Assert
    assert normalize_soft_skill("leadership") == "Leadership"
    assert normalize_soft_skill("LEADERSHIP") == "Leadership"


def test_normalize_soft_skill_returns_none_for_unknown_skill():
    # Act / Assert
    assert normalize_soft_skill("some-made-up-skill") is None
