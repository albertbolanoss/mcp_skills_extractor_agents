"""Tests for orchestrator.py's pure helpers and the agent-session retry loop."""

import json
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock

from mcp_skills_extractor_agents.agents.technical_skills import orchestrator as module
from mcp_skills_extractor_agents.agents.technical_skills.orchestrator import (
    _EvaluatedSkill,
    _extract_json_array,
    _ExtractedSkill,
    _make_batches,
    _synthesize,
    run_technical_skills_pipeline,
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


def test_extract_json_array_strips_markdown_fences():
    # Act
    result = _extract_json_array("```json\n[1, 2]\n```")

    # Assert
    assert result == "[1, 2]"


def test_extract_json_array_raises_when_no_array_found():
    # Act / Assert
    with pytest.raises(ValueError):
        _extract_json_array("no array here")


async def test_ask_ignores_non_assistant_messages(monkeypatch):
    # Arrange
    _mock_agent(monkeypatch, [json.dumps([])], include_non_assistant=True)

    # Act
    result = await run_technical_skills_pipeline("doc", "resume")

    # Assert
    assert result == []


async def test_run_agent_session_raises_after_exhausting_retries(monkeypatch):
    # Arrange
    _mock_agent(monkeypatch, ["still not json", "still not json"])

    # Act / Assert
    with pytest.raises(RuntimeError):
        await run_technical_skills_pipeline("whatever", "resume", max_retries=1)


async def test_run_evaluator_batch_retries_on_length_mismatch(monkeypatch):
    # Arrange
    extracted_json = json.dumps(
        [
            {
                "skill": "Python",
                "evidence_text": "Python experience",
                "justification": "mentions Python",
            }
        ]
    )
    mismatched = json.dumps([])  # 0 items, expected 1 -> triggers a correction retry
    corrected = json.dumps(
        [{"skill": "Python", "accuracy": 1.0, "evaluator_justification": "confirmed"}]
    )
    sessions = iter([[extracted_json], [mismatched, corrected]])

    monkeypatch.setattr(
        module,
        "ClaudeSDKClient",
        lambda options=None: _FakeClient(next(sessions), options),
    )
    monkeypatch.setattr(
        module, "get_agent_environment", lambda settings: SimpleNamespace(env={})
    )

    # Act
    result = await run_technical_skills_pipeline(
        "Python experience", "resume", max_retries=1
    )

    # Assert
    assert result == [
        {
            "skill": "Python",
            "evidences": {
                "technical_skills": {
                    "text": "Python experience",
                    "accuracy": 1.0,
                    "justification": "mentions Python",
                    "evaluator_justification": "confirmed",
                }
            },
        }
    ]


def test_make_batches_splits_into_chunks_of_size():
    # Act
    result = _make_batches(list(range(7)), 3)

    # Assert
    assert result == [[0, 1, 2], [3, 4, 5], [6]]


def test_synthesize_keeps_required_for_job_posting():
    # Arrange
    extracted = [
        _ExtractedSkill(
            skill="Python", evidence_text="Must know Python", justification="mandatory"
        )
    ]
    evaluated = [
        _EvaluatedSkill(
            skill="Python",
            required=True,
            accuracy=1.0,
            evaluator_justification="confirmed",
        )
    ]

    # Act
    result = _synthesize("job_posting", extracted, evaluated)

    # Assert
    assert result[0]["required"] is True


def test_synthesize_normalizes_seniority_level_when_present():
    # Arrange
    extracted = [
        _ExtractedSkill(
            skill="JS", evidence_text="Senior JS engineer", justification="title"
        )
    ]
    evaluated = [
        _EvaluatedSkill(
            skill="JS",
            seniority_level="Sr",
            accuracy=1.0,
            evaluator_justification="confirmed",
        )
    ]

    # Act
    result = _synthesize("resume", extracted, evaluated)

    # Assert
    assert result[0]["skill"] == "JavaScript"
    assert result[0]["seniority_level"] == "Senior"


def test_synthesize_forces_required_none_for_resume():
    # Arrange
    extracted = [
        _ExtractedSkill(skill="Python", evidence_text="Python", justification="j")
    ]
    evaluated = [
        _EvaluatedSkill(
            skill="Python",
            required=True,
            accuracy=1.0,
            evaluator_justification="confirmed",
        )
    ]

    # Act
    result = _synthesize("resume", extracted, evaluated)

    # Assert
    assert "required" not in result[0]
