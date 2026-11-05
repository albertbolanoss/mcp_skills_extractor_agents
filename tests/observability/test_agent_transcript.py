"""Tests for the agent transcript writer."""

import json
from pathlib import Path

from mcp_skills_extractor_agents.observability import AgentTranscriptWriter
from mcp_skills_extractor_agents.settings import SkillAgentSettings


def _settings(tmp_path: Path, observability_enabled: bool = True) -> SkillAgentSettings:
    return SkillAgentSettings(
        observability_enabled=observability_enabled,
        agent_transcript_dir=str(tmp_path / "agent_transcript"),
    )


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def test_session_start_writes_the_system_prompt_once(tmp_path: Path):
    # Arrange
    writer = AgentTranscriptWriter(_settings(tmp_path))

    # Act
    writer.session_start(
        "corr-1",
        "extract_technical_skills",
        model="us.anthropic.claude-sonnet-5",
        system_prompt="You are a precise IT technical-skill extraction specialist.",
        user_prompt="Document type: resume\n\n...",
    )

    # Assert
    lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-1__extract_technical_skills.jsonl"
    )
    assert len(lines) == 1
    event = lines[0]
    assert event["correlation_id"] == "corr-1"
    assert event["service"] == "mcp_skills_extractor_agents"
    assert event["agent"] == "extract_technical_skills"
    assert event["event"] == "session_start"
    assert event["system_prompt"] == "You are a precise IT technical-skill extraction specialist."
    assert event["session_id"] is None


async def test_assistant_text_writes_the_raw_response_and_session_id(tmp_path: Path):
    # Arrange
    writer = AgentTranscriptWriter(_settings(tmp_path))

    # Act
    writer.assistant_text(
        "corr-2", "extract_soft_skills", text='[{"skill": "Leadership"}]', session_id="session-1"
    )

    # Assert
    lines = _read_lines(tmp_path / "agent_transcript" / "corr-2__extract_soft_skills.jsonl")
    assert lines[0]["event"] == "assistant_text"
    assert lines[0]["text"] == '[{"skill": "Leadership"}]'
    assert lines[0]["session_id"] == "session-1"


async def test_retry_writes_the_validation_error(tmp_path: Path):
    # Arrange
    writer = AgentTranscriptWriter(_settings(tmp_path))

    # Act
    writer.retry(
        "corr-3",
        "extract_certifications",
        attempt=1,
        attempts=3,
        error="No JSON array found in the agent's response",
    )

    # Assert
    lines = _read_lines(
        tmp_path / "agent_transcript" / "corr-3__extract_certifications.jsonl"
    )
    assert lines[0]["event"] == "retry"
    assert lines[0]["attempt"] == 1
    assert lines[0]["attempts"] == 3
    assert lines[0]["error"] == "No JSON array found in the agent's response"


async def test_session_end_writes_the_successful_result(tmp_path: Path):
    # Arrange
    writer = AgentTranscriptWriter(_settings(tmp_path))

    # Act
    writer.session_end(
        "corr-4", "extract_languages", is_error=False, result=[{"language": "English"}]
    )

    # Assert
    lines = _read_lines(tmp_path / "agent_transcript" / "corr-4__extract_languages.jsonl")
    assert lines[0]["event"] == "session_end"
    assert lines[0]["is_error"] is False
    assert lines[0]["result"] == [{"language": "English"}]
    assert lines[0]["error"] is None


async def test_session_end_writes_the_failure_error(tmp_path: Path):
    # Arrange
    writer = AgentTranscriptWriter(_settings(tmp_path))

    # Act
    writer.session_end(
        "corr-5", "extract_languages", is_error=True, error="agent failed after 3 attempts"
    )

    # Assert
    lines = _read_lines(tmp_path / "agent_transcript" / "corr-5__extract_languages.jsonl")
    assert lines[0]["is_error"] is True
    assert lines[0]["result"] is None
    assert lines[0]["error"] == "agent failed after 3 attempts"


async def test_events_for_the_same_tool_call_append_in_order(tmp_path: Path):
    # Arrange
    writer = AgentTranscriptWriter(_settings(tmp_path))

    # Act
    writer.assistant_text("corr-6", "extract_languages", text="first")
    writer.assistant_text("corr-6", "extract_languages", text="second")

    # Assert
    lines = _read_lines(tmp_path / "agent_transcript" / "corr-6__extract_languages.jsonl")
    assert [line["text"] for line in lines] == ["first", "second"]


async def test_every_event_is_a_noop_when_observability_is_disabled(tmp_path: Path):
    # Arrange
    writer = AgentTranscriptWriter(_settings(tmp_path, observability_enabled=False))

    # Act
    writer.session_start(
        "corr-7", "extract_languages", model="x", system_prompt="x", user_prompt="x"
    )
    writer.assistant_text("corr-7", "extract_languages", text="x")
    writer.retry("corr-7", "extract_languages", attempt=1, attempts=1, error="x")
    writer.session_end("corr-7", "extract_languages", is_error=False)

    # Assert
    assert not (tmp_path / "agent_transcript").exists()
