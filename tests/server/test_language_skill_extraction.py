"""Tests for the Claude-agent-backed languages extraction tool."""

import json
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock

from candidate_skill_agent.server.tools import language_skill_extraction as module
from candidate_skill_agent.server.tools.language_skill_extraction import (
    extract_languages,
)


class _FakeClient:
    """Fakes ClaudeSDKClient: replays queued agent text responses, one per query() call."""

    def __init__(self, responses: list[str], options=None):
        self._responses = iter(responses)
        self.options = options
        self.prompts: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def query(self, prompt: str) -> None:
        self.prompts.append(prompt)

    async def receive_response(self):
        yield AssistantMessage(
            content=[TextBlock(text=next(self._responses))], model="sonnet"
        )


def _mock_agent(monkeypatch, responses: list[str]) -> None:
    monkeypatch.setattr(
        module, "ClaudeSDKClient", lambda options=None: _FakeClient(responses, options)
    )
    monkeypatch.setattr(
        module, "get_agent_environment", lambda settings: SimpleNamespace(env={})
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
    assert result == [
        {"language": "English", "proficiency": "B2", "is_native": False}
    ]


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
    assert result == [
        {"language": "Spanish", "proficiency": "C2", "is_native": True}
    ]


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
    assert result == [
        {"language": "French", "proficiency": "B1", "is_native": False}
    ]


async def test_extract_languages_raises_after_exhausting_retries(monkeypatch):
    # Arrange
    _mock_agent(monkeypatch, ["still not json", "still not json"])

    # Act / Assert
    with pytest.raises(RuntimeError):
        await extract_languages("whatever", "resume", max_retries=1)
