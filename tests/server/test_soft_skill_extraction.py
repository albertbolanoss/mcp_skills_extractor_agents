"""Tests for the Claude-agent-backed soft-skills extraction tool."""

import json
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock

from candidate_skill_agent.server.tools import soft_skill_extraction as module
from candidate_skill_agent.server.tools.soft_skill_extraction import extract_soft_skills


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


async def test_extract_soft_skills_resume_omits_required(monkeypatch):
    # Arrange
    agent_json = json.dumps(
        [{"skill": "Team Player", "seniority_level": "Sr", "experience_years": 5}]
    )
    _mock_agent(monkeypatch, [agent_json])

    # Act
    result = await extract_soft_skills("Led the team for 5 years", "resume")

    # Assert
    assert result == [
        {"skill": "Teamwork", "seniority_level": "Senior", "experience_years": 5}
    ]


async def test_extract_soft_skills_job_posting_includes_required(monkeypatch):
    # Arrange
    agent_json = json.dumps(
        [
            {
                "skill": "Leadership",
                "seniority_level": "Senior-Level",
                "experience_years": 5,
                "required": True,
            }
        ]
    )
    _mock_agent(monkeypatch, [agent_json])

    # Act
    result = await extract_soft_skills("Must demonstrate leadership", "job_posting")

    # Assert
    assert result == [
        {
            "skill": "Leadership",
            "seniority_level": "Senior",
            "experience_years": 5,
            "required": True,
        }
    ]


async def test_extract_soft_skills_retries_on_invalid_json(monkeypatch):
    # Arrange
    responses = [
        "not json",
        json.dumps([{"skill": "Coaching", "seniority_level": "Mid"}]),
    ]
    _mock_agent(monkeypatch, responses)

    # Act
    result = await extract_soft_skills("Mentors junior engineers", "resume", max_retries=1)

    # Assert
    assert result == [{"skill": "Mentoring", "seniority_level": "Mid-Level"}]


async def test_extract_soft_skills_raises_after_exhausting_retries(monkeypatch):
    # Arrange
    _mock_agent(monkeypatch, ["still not json", "still not json"])

    # Act / Assert
    with pytest.raises(RuntimeError):
        await extract_soft_skills("whatever", "resume", max_retries=1)
