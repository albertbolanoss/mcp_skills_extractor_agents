"""Tests for the Claude-agent-backed technical-skills extraction tool."""

import json
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from mcp_skills_extractor_agents.server.tools import (
    technical_skill_extraction as module,
)
from mcp_skills_extractor_agents.server.tools.technical_skill_extraction import (
    extract_technical_skills,
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
) -> list[_FakeClient]:
    """Wires the fake client/settings into `module` and returns the created clients,
    one per `ClaudeSDKClient(...)` call, so a test can inspect `.options`."""
    clients: list[_FakeClient] = []

    def _make_client(options=None):
        client = _FakeClient(responses, options, include_non_assistant)
        clients.append(client)
        return client

    monkeypatch.setattr(module, "ClaudeSDKClient", _make_client)
    monkeypatch.setattr(
        module, "get_agent_environment", lambda settings: SimpleNamespace(env={})
    )
    monkeypatch.setattr(
        module, "get_skill_agent_settings", lambda: _FakeSkillAgentSettings()
    )
    return clients


async def test_extract_technical_skills_resume_omits_required(monkeypatch):
    # Arrange
    agent_json = json.dumps(
        [{"skill": "JS", "seniority_level": "Sr", "experience_years": 5}]
    )
    _mock_agent(monkeypatch, [agent_json])

    # Act
    result = await extract_technical_skills("Used JS for 5 years", "resume")

    # Assert
    assert result == [
        {"skill": "JavaScript", "seniority_level": "Senior", "experience_years": 5}
    ]


async def test_extract_technical_skills_job_posting_includes_required(monkeypatch):
    # Arrange
    agent_json = json.dumps(
        [
            {
                "skill": "Python3",
                "seniority_level": "Senior-Level",
                "experience_years": 5,
                "required": True,
            }
        ]
    )
    _mock_agent(monkeypatch, [agent_json])

    # Act
    result = await extract_technical_skills("Must know Python", "job_posting")

    # Assert
    assert result == [
        {
            "skill": "Python",
            "seniority_level": "Senior",
            "experience_years": 5,
            "required": True,
        }
    ]


async def test_extract_technical_skills_retries_on_invalid_json(monkeypatch):
    # Arrange
    responses = ["not json", json.dumps([{"skill": "Go", "seniority_level": "Mid"}])]
    _mock_agent(monkeypatch, responses)

    # Act
    result = await extract_technical_skills("Go developer", "resume", max_retries=1)

    # Assert
    assert result == [{"skill": "Go", "seniority_level": "Mid-Level"}]


async def test_extract_technical_skills_strips_markdown_code_fences(monkeypatch):
    # Arrange
    agent_json = json.dumps([{"skill": "Go", "seniority_level": "Mid"}])
    _mock_agent(monkeypatch, [f"```json\n{agent_json}\n```"])

    # Act
    result = await extract_technical_skills("Go developer", "resume")

    # Assert
    assert result == [{"skill": "Go", "seniority_level": "Mid-Level"}]


async def test_extract_technical_skills_ignores_non_assistant_messages(monkeypatch):
    # Arrange
    agent_json = json.dumps([{"skill": "Go", "seniority_level": "Mid"}])
    _mock_agent(monkeypatch, [agent_json], include_non_assistant=True)

    # Act
    result = await extract_technical_skills("Go developer", "resume")

    # Assert
    assert result == [{"skill": "Go", "seniority_level": "Mid-Level"}]


async def test_extract_technical_skills_raises_after_exhausting_retries(monkeypatch):
    # Arrange
    _mock_agent(monkeypatch, ["still not json", "still not json"])

    # Act / Assert
    with pytest.raises(RuntimeError):
        await extract_technical_skills("whatever", "resume", max_retries=1)


async def test_extract_technical_skills_uses_low_effort(monkeypatch):
    # Arrange
    agent_json = json.dumps([{"skill": "Go", "seniority_level": "Mid"}])
    clients = _mock_agent(monkeypatch, [agent_json])

    # Act
    await extract_technical_skills("Go developer", "resume")

    # Assert
    assert clients[0].options.effort == "medium"
