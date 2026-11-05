"""Acceptance tests for the technical-skills Generator-Evaluator-Synthesizer pipeline.

Each test here maps 1:1 to a verification criterion from
`spec/11-04-26-01-technical_skills_extraction.spec.md` section 8.
"""

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock
from pydantic import ValidationError

from mcp_skills_extractor_agents.agents.technical_skills import orchestrator as module
from mcp_skills_extractor_agents.agents.technical_skills.orchestrator import (
    run_technical_skills_pipeline,
)
from mcp_skills_extractor_agents.agents.technical_skills.schemas import (
    EvidenceContainer,
    TechnicalSkillEvidence,
    TechnicalSkillItem,
)
from mcp_skills_extractor_agents.server.tools import (
    technical_skill_extraction as tool_module,
)


class _FakeClient:
    """Fakes ClaudeSDKClient: replays queued agent text responses for one session,
    one response per query() call.
    """

    def __init__(self, responses: list[str]):
        self._responses = iter(responses)
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


def _client_factory(sessions: list[list[str]]):
    """Returns a ClaudeSDKClient-shaped factory handing out one `_FakeClient` per call,
    fed from the next entry of `sessions` in call order (one entry per agent session:
    the extractor, then each evaluator batch).
    """
    sessions_iter = iter(sessions)
    created: list[_FakeClient] = []

    def _factory(options=None):
        client = _FakeClient(next(sessions_iter))
        created.append(client)
        return client

    _factory.created = created
    return _factory


def _mock_sessions(monkeypatch, sessions: list[list[str]]):
    factory = _client_factory(sessions)
    monkeypatch.setattr(module, "ClaudeSDKClient", factory)
    monkeypatch.setattr(
        module, "get_agent_environment", lambda settings: SimpleNamespace(env={})
    )
    return factory


def test_module_separation():
    # Arrange
    source = Path(inspect.getfile(tool_module)).read_text(encoding="utf-8")

    # Act / Assert
    assert "run_technical_skills_pipeline" in source
    assert "agents.technical_skills" in source
    assert "ClaudeSDKClient" not in source
    assert "AgentDefinition" not in source


def test_partial_attributes_allowed():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        evidences=EvidenceContainer(
            technical_skills=TechnicalSkillEvidence(
                text="Used Python", justification="mentions Python"
            )
        ),
    )

    # Assert
    assert item.seniority_level is None
    assert item.experience_years is None
    assert item.required is None
    assert item.evidences.technical_skills.accuracy == -1.0
    assert item.evidences.technical_skills.evaluator_justification is None

    # Act / Assert - "skill" and "evidences" remain required
    with pytest.raises(ValidationError):
        TechnicalSkillItem(seniority_level="Senior")


async def test_empty_extraction_short_circuits_evaluator(monkeypatch):
    # Arrange
    factory = _mock_sessions(monkeypatch, [["[]"]])

    # Act
    result = await run_technical_skills_pipeline("no tech skills here", "resume")

    # Assert
    assert result == []
    assert len(factory.created) == 1


async def test_batch_evaluation_concurrency(monkeypatch):
    # Arrange
    extracted_items = [
        {
            "skill": f"Skill{i}",
            "evidence_text": f"text {i}",
            "justification": f"justification {i}",
        }
        for i in range(25)
    ]

    def _evaluated_batch(size: int) -> str:
        return json.dumps(
            [
                {
                    "skill": f"Skill{i}",
                    "accuracy": 1.0,
                    "evaluator_justification": "confirmed",
                }
                for i in range(size)
            ]
        )

    factory = _mock_sessions(
        monkeypatch,
        [
            [json.dumps(extracted_items)],
            [_evaluated_batch(10)],
            [_evaluated_batch(10)],
            [_evaluated_batch(5)],
        ],
    )

    # Act
    result = await run_technical_skills_pipeline("25 skills doc", "resume")

    # Assert
    assert len(result) == 25
    assert len(factory.created) == 4  # 1 extractor session + 3 evaluator batch sessions


async def test_evaluator_nullifies_unsupported_metadata(monkeypatch):
    # Arrange
    extracted = [
        {
            "skill": "Python",
            "seniority_level": "Senior",
            "experience_years": 5,
            "evidence_text": "Experience with Python",
            "justification": "mentions Python",
        }
    ]
    evaluated = [
        {
            "skill": "Python",
            "seniority_level": None,
            "experience_years": None,
            "accuracy": 0.9,
            "evaluator_justification": (
                "Skill verified, but seniority and years were not stated in the "
                "source text"
            ),
        }
    ]
    _mock_sessions(monkeypatch, [[json.dumps(extracted)], [json.dumps(evaluated)]])

    # Act
    result = await run_technical_skills_pipeline("Experience with Python", "resume")

    # Assert
    assert len(result) == 1
    item = result[0]
    assert item["skill"] == "Python"
    assert "seniority_level" not in item
    assert "experience_years" not in item
    assert item["evidences"]["technical_skills"]["accuracy"] == 0.9
    assert item["evidences"]["technical_skills"]["evaluator_justification"] == (
        "Skill verified, but seniority and years were not stated in the source text"
    )


async def test_synthesizer_filters_low_accuracy_skills(monkeypatch):
    # Arrange
    extracted = [
        {
            "skill": "Python",
            "evidence_text": "Experience with Python",
            "justification": "mentions Python",
        },
        {
            "skill": "Kubernetes",
            "evidence_text": "Experience with Docker",
            "justification": "assumed from Docker",
        },
    ]
    evaluated = [
        {
            "skill": "Python",
            "accuracy": 0.85,
            "evaluator_justification": "confirmed",
        },
        {
            "skill": "Kubernetes",
            "accuracy": 0.4,
            "evaluator_justification": "document only mentions Docker, not Kubernetes",
        },
    ]
    _mock_sessions(monkeypatch, [[json.dumps(extracted)], [json.dumps(evaluated)]])

    # Act
    result = await run_technical_skills_pipeline(
        "Experience with Python and Docker", "resume"
    )

    # Assert
    assert len(result) == 1
    assert result[0]["skill"] == "Python"


async def test_retry_loop_recovers_from_malformed_json(monkeypatch):
    # Arrange
    factory = _mock_sessions(monkeypatch, [["not json", "[]"]])

    # Act
    result = await run_technical_skills_pipeline(
        "ambiguous text", "resume", max_retries=1
    )

    # Assert
    assert result == []
    assert len(factory.created) == 1
    client = factory.created[0]
    assert len(client.prompts) == 2
    assert "not valid JSON" in client.prompts[1]
