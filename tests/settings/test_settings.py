"""Tests for the Candidate Skill Agent settings."""

from mcp_skills_extractor_agents.settings import SkillAgentSettings, ToolName


def test_active_tools_defaults_to_none():
    # Act
    settings = SkillAgentSettings()

    # Assert
    assert settings.active_tools is None


def test_active_tools_accepts_comma_separated_string():
    # Act
    settings = SkillAgentSettings(
        active_tools="extract_technical_skills, extract_certifications"
    )

    # Assert
    assert settings.active_tools == frozenset(
        {ToolName.TECHNICAL_SKILLS, ToolName.CERTIFICATIONS}
    )


def test_active_tools_accepts_real_collection():
    # Act
    settings = SkillAgentSettings(active_tools=[ToolName.LANGUAGES])

    # Assert
    assert settings.active_tools == frozenset({ToolName.LANGUAGES})


def test_observability_settings_default():
    # Act
    settings = SkillAgentSettings()

    # Assert
    assert settings.observability_enabled is True
    assert settings.prompt_log_dir == "documentation/prompt_log"
    assert settings.agent_transcript_dir == "documentation/agent_transcript"
