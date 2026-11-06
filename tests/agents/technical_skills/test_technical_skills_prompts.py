"""Tests for the technical-skills prompt builders and static system prompts."""

from mcp_skills_extractor_agents.agents.technical_skills.prompts import (
    EVALUATOR_CORRECTION_PROMPT,
    EVALUATOR_SYSTEM_PROMPT,
    EXTRACTOR_CORRECTION_PROMPT,
    EXTRACTOR_SYSTEM_PROMPT,
    _strip_for_evaluation,
    build_evaluator_user_prompt,
    build_extractor_user_prompt,
)
from mcp_skills_extractor_agents.agents.technical_skills.schemas import (
    TechnicalSkillItem,
)


def test_extractor_system_prompt_embeds_the_canonical_taxonomies():
    # Act / Assert
    assert "PostgreSQL" in EXTRACTOR_SYSTEM_PROMPT
    assert "Senior" in EXTRACTOR_SYSTEM_PROMPT


def test_evaluator_system_prompt_does_not_embed_the_skill_taxonomy():
    # Act / Assert
    assert "PostgreSQL" not in EVALUATOR_SYSTEM_PROMPT


def test_build_extractor_user_prompt_wraps_document_and_doc_type():
    # Act
    prompt = build_extractor_user_prompt("5 years of Python", "resume")

    # Assert
    assert "Document type: resume" in prompt
    assert "5 years of Python" in prompt


def test_strip_for_evaluation_drops_accuracy_and_evaluator_justification():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        evidences={
            "skill": {
                "grounding_text": "Python",
                "justification": "stated",
                "accuracy": 1.0,
                "evaluator_justification": "should be dropped",
            }
        },
    )

    # Act
    stripped = _strip_for_evaluation(item)

    # Assert
    assert "accuracy" not in stripped["evidences"]["skill"]
    assert "evaluator_justification" not in stripped["evidences"]["skill"]
    assert stripped["evidences"]["required"] is None


def test_build_evaluator_user_prompt_embeds_stripped_batch_and_document():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        evidences={"skill": {"grounding_text": "Python", "justification": "stated"}},
    )

    # Act
    prompt = build_evaluator_user_prompt([item], "resume text here", "resume")
    header = prompt.split("--- SOURCE DOCUMENT START ---")[0]

    # Assert
    assert "resume text here" in prompt
    assert "Document type: resume" in prompt
    assert '"skill": "Python"' in prompt
    assert "accuracy" not in header


def test_correction_prompts_format_with_the_validation_error():
    # Act / Assert
    assert "boom" in EXTRACTOR_CORRECTION_PROMPT.format(error="boom")
    assert "boom" in EVALUATOR_CORRECTION_PROMPT.format(error="boom")
