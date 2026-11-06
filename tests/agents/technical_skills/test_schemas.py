"""Tests for the technical-skills Pydantic v2 schema hydration validators."""

from mcp_skills_extractor_agents.agents.technical_skills.schemas import (
    DEFAULT_NULL_JUSTIFICATION,
    FieldEvidence,
    SkillEvidences,
    TechnicalSkillItem,
)


def test_field_evidence_hydrates_missing_justification():
    # Act
    item = TechnicalSkillItem(
        skill="Python", evidences={"skill": {"grounding_text": "Python"}}
    )

    # Assert
    assert item.evidences.skill.justification == DEFAULT_NULL_JUSTIFICATION


def test_field_evidence_hydrates_blank_justification():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        evidences={"skill": {"grounding_text": "Python", "justification": "   "}},
    )

    # Assert
    assert item.evidences.skill.justification == DEFAULT_NULL_JUSTIFICATION


def test_field_evidence_keeps_an_explicit_non_blank_justification():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        evidences={"skill": {"grounding_text": "Python", "justification": "stated"}},
    )

    # Assert
    assert item.evidences.skill.justification == "stated"


def test_field_evidence_before_validator_passes_through_non_dict_data():
    """Pydantic's default `revalidate_instances='never'` means an already-built
    FieldEvidence instance never reaches this validator as non-dict `data` through the
    public API - so the passthrough branch (resilience against a future caller that
    validates raw non-dict input) is exercised directly against the validator."""
    # Act / Assert
    assert FieldEvidence._hydrate_defaults("not-a-dict") == "not-a-dict"


def test_skill_evidences_before_validator_passes_through_non_dict_data():
    # Act / Assert
    assert SkillEvidences._ensure_secondary_evidences("not-a-dict") == "not-a-dict"


def test_skill_evidences_fills_in_missing_secondary_fields():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        evidences={"skill": {"grounding_text": "Python", "justification": "x"}},
    )

    # Assert
    assert item.evidences.seniority_level.grounding_text == ""
    assert item.evidences.seniority_level.justification == DEFAULT_NULL_JUSTIFICATION
    assert item.evidences.experience_years.grounding_text == ""
    assert item.evidences.experience_years.justification == DEFAULT_NULL_JUSTIFICATION


def test_skill_evidences_hydrates_explicit_null_secondary_fields():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        evidences={
            "skill": {"grounding_text": "Python", "justification": "x"},
            "seniority_level": None,
            "experience_years": None,
        },
    )

    # Assert
    assert item.evidences.seniority_level.grounding_text == ""
    assert item.evidences.experience_years.grounding_text == ""
