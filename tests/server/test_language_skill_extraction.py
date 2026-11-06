"""Tests for the Claude-agent-backed languages extraction tool."""

import json
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from mcp_skills_extractor_agents.server.tools import language_skill_extraction as module
from mcp_skills_extractor_agents.server.tools.language_skill_extraction import (
    extract_languages,
)


class _FakeClient:
    """Fakes ClaudeSDKClient: replays queued agent text responses, one per query() call."""

    def __init__(
        self, responses: list[str], options=None, include_non_assistant: bool = False
    ):
        self._responses = iter(responses)
        self.options = options
        self.prompts: list[str] = []
        self._include_non_assistant = include_non_assistant

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def query(self, prompt: str) -> None:
        self.prompts.append(prompt)

    async def receive_response(self):
        if self._include_non_assistant:
            yield object()
        yield AssistantMessage(
            content=[TextBlock(text=next(self._responses))], model="sonnet"
        )
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-fake",
        )


class _FakeSkillAgentSettings:
    """Keeps the new observability writers a no-op for these extraction-focused tests."""

    observability_enabled = False
    prompt_log_dir = "unused"
    agent_transcript_dir = "unused"


def _mock_agent(
    monkeypatch, responses: list[str], include_non_assistant: bool = False
) -> None:
    monkeypatch.setattr(
        module,
        "ClaudeSDKClient",
        lambda options=None: _FakeClient(responses, options, include_non_assistant),
    )
    monkeypatch.setattr(
        module, "get_agent_environment", lambda settings: SimpleNamespace(env={})
    )
    monkeypatch.setattr(
        module, "get_skill_agent_settings", lambda: _FakeSkillAgentSettings()
    )


async def test_extract_languages_resume_omits_required(monkeypatch):
    # Arrange
    agent_json = json.dumps(
        [
            {
                "language": "Inglés",
                "proficiency": "Upper Intermediate",
                "is_native": False,
            }
        ]
    )
    _mock_agent(monkeypatch, [agent_json])

    # Act
    result = await extract_languages("English B2 level", "resume")

    # Assert
    assert result == [{"language": "English", "proficiency": "B2", "is_native": False}]


async def test_extract_languages_job_posting_includes_required(monkeypatch):
    # Arrange
    agent_json = json.dumps(
        [
            {
                "language": "English",
                "proficiency": "B2",
                "is_native": False,
                "required": True,
            }
        ]
    )
    _mock_agent(monkeypatch, [agent_json])

    # Act
    result = await extract_languages("English B2 required", "job_posting")

    # Assert
    assert result == [
        {
            "language": "English",
            "proficiency": "B2",
            "is_native": False,
            "required": True,
        }
    ]


async def test_extract_languages_normalizes_native_speaker(monkeypatch):
    # Arrange
    agent_json = json.dumps(
        [{"language": "Castellano", "proficiency": "Native", "is_native": True}]
    )
    _mock_agent(monkeypatch, [agent_json])

    # Act
    result = await extract_languages("Native Spanish speaker", "resume")

    # Assert
    assert result == [{"language": "Spanish", "proficiency": "C2", "is_native": True}]


async def test_extract_languages_retries_on_invalid_json(monkeypatch):
    # Arrange
    responses = [
        "not json",
        json.dumps([{"language": "French", "proficiency": "Intermediate"}]),
    ]
    _mock_agent(monkeypatch, responses)

    # Act
    result = await extract_languages("Speaks French", "resume", max_retries=1)

    # Assert
    assert result == [{"language": "French", "proficiency": "B1", "is_native": False}]


async def test_extract_languages_strips_markdown_code_fences(monkeypatch):
    # Arrange
    agent_json = json.dumps([{"language": "French", "proficiency": "Intermediate"}])
    _mock_agent(monkeypatch, [f"```json\n{agent_json}\n```"])

    # Act
    result = await extract_languages("Speaks French", "resume")

    # Assert
    assert result == [{"language": "French", "proficiency": "B1", "is_native": False}]


async def test_extract_languages_ignores_non_assistant_messages(monkeypatch):
    # Arrange
    agent_json = json.dumps([{"language": "French", "proficiency": "Intermediate"}])
    _mock_agent(monkeypatch, [agent_json], include_non_assistant=True)

    # Act
    result = await extract_languages("Speaks French", "resume")

    # Assert
    assert result == [{"language": "French", "proficiency": "B1", "is_native": False}]


async def test_extract_languages_raises_after_exhausting_retries(monkeypatch):
    # Arrange
    _mock_agent(monkeypatch, ["still not json", "still not json"])

    # Act / Assert
    with pytest.raises(RuntimeError):
        await extract_languages("whatever", "resume", max_retries=1)
