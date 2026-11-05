"""Tests for the prompt log writer."""

import json
from pathlib import Path

from mcp_skills_extractor_agents.observability import PromptLogWriter
from mcp_skills_extractor_agents.settings import SkillAgentSettings


def _settings(tmp_path: Path, observability_enabled: bool = True) -> SkillAgentSettings:
    return SkillAgentSettings(
        observability_enabled=observability_enabled,
        prompt_log_dir=str(tmp_path / "prompt_log"),
    )


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def test_log_prompt_writes_one_jsonl_line_with_the_expected_fields(tmp_path: Path):
    # Arrange
    writer = PromptLogWriter(_settings(tmp_path))

    # Act
    writer.log_prompt(
        correlation_id="corr-1",
        tool_name="extract_technical_skills",
        model="us.anthropic.claude-sonnet-5",
        system_prompt_name="extract_technical_skills",
        user_prompt="Document type: resume\n\n...",
        attempt=1,
    )

    # Assert
    lines = _read_lines(tmp_path / "prompt_log" / "corr-1__extract_technical_skills.jsonl")
    assert len(lines) == 1
    assert lines[0]["correlation_id"] == "corr-1"
    assert lines[0]["service"] == "mcp_skills_extractor_agents"
    assert lines[0]["agent"] == "extract_technical_skills"
    assert lines[0]["event"] == "prompt"
    assert lines[0]["model"] == "us.anthropic.claude-sonnet-5"
    assert lines[0]["attempt"] == 1
    assert "timestamp" in lines[0]


async def test_log_prompt_keys_each_tool_into_its_own_file_for_the_same_correlation_id(
    tmp_path: Path,
):
    # Arrange
    writer = PromptLogWriter(_settings(tmp_path))

    # Act
    writer.log_prompt(
        correlation_id="corr-2",
        tool_name="extract_technical_skills",
        model="model-x",
        system_prompt_name="extract_technical_skills",
        user_prompt="a",
    )
    writer.log_prompt(
        correlation_id="corr-2",
        tool_name="extract_soft_skills",
        model="model-x",
        system_prompt_name="extract_soft_skills",
        user_prompt="b",
    )

    # Assert
    assert (tmp_path / "prompt_log" / "corr-2__extract_technical_skills.jsonl").exists()
    assert (tmp_path / "prompt_log" / "corr-2__extract_soft_skills.jsonl").exists()


async def test_log_prompt_falls_back_to_a_placeholder_when_no_correlation_id_is_given(
    tmp_path: Path,
):
    # Arrange
    writer = PromptLogWriter(_settings(tmp_path))

    # Act
    writer.log_prompt(
        correlation_id="",
        tool_name="extract_technical_skills",
        model="model-x",
        system_prompt_name="extract_technical_skills",
        user_prompt="a",
    )

    # Assert
    lines = _read_lines(
        tmp_path / "prompt_log" / "no-correlation-id__extract_technical_skills.jsonl"
    )
    assert lines[0]["correlation_id"] == ""


async def test_log_prompt_is_a_noop_when_observability_is_disabled(tmp_path: Path):
    # Arrange
    writer = PromptLogWriter(_settings(tmp_path, observability_enabled=False))

    # Act
    writer.log_prompt(
        correlation_id="corr-3",
        tool_name="extract_technical_skills",
        model="model-x",
        system_prompt_name="extract_technical_skills",
        user_prompt="irrelevant",
    )

    # Assert
    assert not (tmp_path / "prompt_log").exists()
