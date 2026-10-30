"""Tests for the MCP prompts."""

from candidate_skill_agent.server.prompts.coordinator_orchestration import (
    coordinator_orchestration,
)


def test_coordinator_orchestration_prompt_references_all_tools():
    # Act
    prompt = coordinator_orchestration()

    # Assert
    assert "extract_technical_skills" in prompt
    assert "extract_soft_skills" in prompt
    assert "extract_certifications" in prompt
    assert "extract_languages" in prompt
    assert "DONE" in prompt
