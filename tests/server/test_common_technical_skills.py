"""Tests for the common-technical-skills MCP resource."""

from candidate_skill_agent.server.resources.common_technical_skills import (
    COMMON_TECHNICAL_SKILLS,
    common_technical_skills,
    normalize_technical_skill,
)


def test_common_technical_skills_has_multiple_categories_and_skills():
    # Act
    taxonomy = common_technical_skills()

    # Assert
    assert taxonomy is COMMON_TECHNICAL_SKILLS
    assert len(taxonomy) > 10
    assert all(len(skills) > 0 for skills in taxonomy.values())


def test_normalize_technical_skill_resolves_known_alias():
    # Act / Assert
    assert normalize_technical_skill("JS") == "JavaScript"
    assert normalize_technical_skill("postgres") == "PostgreSQL"
    assert normalize_technical_skill("  K8s ") == "Kubernetes"


def test_normalize_technical_skill_is_case_insensitive_on_canonical_name():
    # Act / Assert
    assert normalize_technical_skill("python") == "Python"
    assert normalize_technical_skill("PYTHON") == "Python"


def test_normalize_technical_skill_returns_none_for_unknown_skill():
    # Act / Assert
    assert normalize_technical_skill("some-made-up-skill") is None
