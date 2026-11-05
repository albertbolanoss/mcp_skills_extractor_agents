"""Tests for the `ToolObservability` recorder that wires one extraction tool call."""

import json
from pathlib import Path

from mcp_skills_extractor_agents.observability import ToolObservability
from mcp_skills_extractor_agents.settings import SkillAgentSettings


def _settings(tmp_path: Path) -> SkillAgentSettings:
    return SkillAgentSettings(
        observability_enabled=True,
        prompt_log_dir=str(tmp_path / "prompt_log"),
        agent_transcript_dir=str(tmp_path / "agent_transcript"),
    )


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def test_first_attempt_writes_a_prompt_line_and_a_session_start_event(tmp_path: Path):
    # Arrange
    observability = ToolObservability(
        _settings(tmp_path),
        tool_name="extract_technical_skills",
        correlation_id="corr-1",
        model="model-x",
        system_prompt="You are a precise IT technical-skill extraction specialist.",
    )

    # Act
    observability.log_attempt_prompt(prompt="Document type: resume\n\n...", attempt=1)

    # Assert
    prompt_lines = _read_lines(
        tmp_path / "prompt_log" / "corr-1__extract_technical_skills.jsonl"
    )
    assert prompt_lines[0]["attempt"] == 1

    transcript_lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-1__extract_technical_skills.jsonl"
    )
    assert transcript_lines[0]["event"] == "session_start"
    assert transcript_lines[0]["system_prompt"] == (
        "You are a precise IT technical-skill extraction specialist."
    )


async def test_a_retry_attempt_writes_a_prompt_line_but_no_second_session_start(tmp_path: Path):
    # Arrange
    observability = ToolObservability(
        _settings(tmp_path),
        tool_name="extract_technical_skills",
        correlation_id="corr-2",
        model="model-x",
        system_prompt="x",
    )

    # Act
    observability.log_attempt_prompt(prompt="first attempt", attempt=1)
    observability.log_attempt_prompt(prompt="corrected attempt", attempt=2)

    # Assert
    prompt_lines = _read_lines(
        tmp_path / "prompt_log" / "corr-2__extract_technical_skills.jsonl"
    )
    assert [line["attempt"] for line in prompt_lines] == [1, 2]

    transcript_lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-2__extract_technical_skills.jsonl"
    )
    assert [line["event"] for line in transcript_lines] == ["session_start"]


async def test_log_attempt_response_writes_the_raw_text(tmp_path: Path):
    # Arrange
    observability = ToolObservability(
        _settings(tmp_path),
        tool_name="extract_technical_skills",
        correlation_id="corr-3",
        model="model-x",
        system_prompt="x",
    )

    # Act
    observability.log_attempt_response(text='[{"skill": "Python"}]', session_id="session-1")

    # Assert
    lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-3__extract_technical_skills.jsonl"
    )
    assert lines[0]["event"] == "assistant_text"
    assert lines[0]["text"] == '[{"skill": "Python"}]'
    assert lines[0]["session_id"] == "session-1"


async def test_log_retry_writes_a_retry_event(tmp_path: Path):
    # Arrange
    observability = ToolObservability(
        _settings(tmp_path),
        tool_name="extract_technical_skills",
        correlation_id="corr-4",
        model="model-x",
        system_prompt="x",
    )

    # Act
    observability.log_retry(attempt=1, attempts=3, error="invalid JSON")

    # Assert
    lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-4__extract_technical_skills.jsonl"
    )
    assert lines[0]["event"] == "retry"
    assert lines[0]["error"] == "invalid JSON"


async def test_log_success_writes_a_session_end_event_without_an_error(tmp_path: Path):
    # Arrange
    observability = ToolObservability(
        _settings(tmp_path),
        tool_name="extract_technical_skills",
        correlation_id="corr-5",
        model="model-x",
        system_prompt="x",
    )

    # Act
    observability.log_success(result=[{"skill": "Python"}])

    # Assert
    lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-5__extract_technical_skills.jsonl"
    )
    assert lines[0]["event"] == "session_end"
    assert lines[0]["is_error"] is False
    assert lines[0]["result"] == [{"skill": "Python"}]


async def test_log_failure_writes_a_session_end_event_with_the_error(tmp_path: Path):
    # Arrange
    observability = ToolObservability(
        _settings(tmp_path),
        tool_name="extract_technical_skills",
        correlation_id="corr-6",
        model="model-x",
        system_prompt="x",
    )

    # Act
    observability.log_failure(error="agent failed after 3 attempts")

    # Assert
    lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-6__extract_technical_skills.jsonl"
    )
    assert lines[0]["event"] == "session_end"
    assert lines[0]["is_error"] is True
    assert lines[0]["error"] == "agent failed after 3 attempts"
