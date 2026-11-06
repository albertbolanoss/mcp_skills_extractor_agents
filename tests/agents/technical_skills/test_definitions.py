"""Tests for the technical-skills Extractor/Evaluator agent definitions."""

from mcp_skills_extractor_agents.agents.technical_skills.definitions import (
    EVALUATOR_AGENT_DEFINITION,
    EXTRACTOR_AGENT_DEFINITION,
)


def test_extractor_agent_definition_uses_a_pinned_sonnet_model_id():
    # Act / Assert
    assert EXTRACTOR_AGENT_DEFINITION.model == "us.anthropic.claude-sonnet-5"
    assert EXTRACTOR_AGENT_DEFINITION.tools == []


def test_evaluator_agent_definition_uses_a_pinned_haiku_model_id():
    # Act / Assert
    assert EVALUATOR_AGENT_DEFINITION.model == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert EVALUATOR_AGENT_DEFINITION.tools == []


def test_extractor_and_evaluator_definitions_use_different_models():
    # Act / Assert
    assert EXTRACTOR_AGENT_DEFINITION.model != EVALUATOR_AGENT_DEFINITION.model
