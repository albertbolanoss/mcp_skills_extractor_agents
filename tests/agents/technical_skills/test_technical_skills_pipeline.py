"""Acceptance tests for the technical-skills Generator-Evaluator-Synthesizer pipeline.

Each test here maps 1:1 to a verification criterion from
`spec/1.0_spec_init_technical_skills_agent_workflow.md` section 8.
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
    FieldEvidence,
    SkillEvidences,
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


def _evidence(
    grounding_text: str = "", justification: str = "justification", **extra
) -> dict:
    """Builds one FieldEvidence-shaped dict for a mocked extractor/evaluator response."""
    return {"grounding_text": grounding_text, "justification": justification, **extra}


def _item(skill: str, evidences: dict, **fields) -> dict:
    """Builds one extracted/evaluated item dict: root fields plus its evidences object."""
    return {"skill": skill, **fields, "evidences": evidences}


def test_module_separation():
    # Arrange
    source = Path(inspect.getfile(tool_module)).read_text(encoding="utf-8")

    # Act / Assert
    assert "run_technical_skills_pipeline" in source
    assert "agents.technical_skills" in source
    assert "ClaudeSDKClient" not in source
    assert "AgentDefinition" not in source


def test_field_level_evidences_structure():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Skills: Python, Docker",
                justification="listed in skills section",
            ),
            seniority_level=FieldEvidence(
                justification=(
                    "Listed only in skills section without proficiency descriptor "
                    "or date range."
                )
            ),
            experience_years=FieldEvidence(
                justification=(
                    "Listed only in skills section without proficiency descriptor "
                    "or date range."
                )
            ),
        ),
    )

    # Assert
    assert item.seniority_level is None
    assert item.experience_years is None
    assert item.required is None
    assert item.evidences.required is None
    assert item.evidences.seniority_level.grounding_text == ""
    assert item.evidences.seniority_level.justification != ""
    assert item.evidences.skill.accuracy == -1.0
    assert item.evidences.skill.evaluator_justification is None

    # Act - a job_posting item also carries a "required" FieldEvidence
    job_posting_item = TechnicalSkillItem(
        skill="Python",
        required=True,
        evidences=SkillEvidences(
            skill=FieldEvidence(grounding_text="Must know Python", justification="j"),
            seniority_level=FieldEvidence(justification="not stated"),
            experience_years=FieldEvidence(justification="not stated"),
            required=FieldEvidence(
                grounding_text="Must know Python", justification="stated as mandatory"
            ),
        ),
    )

    # Assert
    assert job_posting_item.evidences.required.grounding_text == "Must know Python"

    # Act / Assert - skill/seniority_level/experience_years evidences remain required
    with pytest.raises(ValidationError):
        SkillEvidences(seniority_level=FieldEvidence(justification="j"))


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
    skills = [f"Skill{i}" for i in range(25)]
    extracted_items = [
        _item(
            skill,
            {
                "skill": _evidence(f"text {skill}", f"justification {skill}"),
                "seniority_level": _evidence(),
                "experience_years": _evidence(),
            },
        )
        for skill in skills
    ]

    def _evaluated_batch(batch_skills: list[str]) -> str:
        return json.dumps(
            [
                _item(
                    skill,
                    {
                        "skill": _evidence(
                            f"text {skill}",
                            f"justification {skill}",
                            accuracy=1.0,
                            evaluator_justification="confirmed",
                        ),
                        "seniority_level": _evidence(
                            accuracy=1.0, evaluator_justification="confirmed abstention"
                        ),
                        "experience_years": _evidence(
                            accuracy=1.0, evaluator_justification="confirmed abstention"
                        ),
                    },
                )
                for skill in batch_skills
            ]
        )

    factory = _mock_sessions(
        monkeypatch,
        [
            [json.dumps(extracted_items)],
            [_evaluated_batch(skills[0:10])],
            [_evaluated_batch(skills[10:20])],
            [_evaluated_batch(skills[20:25])],
        ],
    )

    # Act
    result = await run_technical_skills_pipeline("25 skills doc", "resume")

    # Assert
    assert len(result) == 25
    assert len(factory.created) == 4  # 1 extractor session + 3 evaluator batch sessions


async def test_evaluator_nullifies_unsupported_secondary_field(monkeypatch):
    # Arrange
    extracted = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence("Familiar with Python", "mentions Python"),
                    "seniority_level": _evidence(
                        "Familiar with Python", "assumed senior from context"
                    ),
                    "experience_years": _evidence(),
                },
                seniority_level="Senior",
            )
        ]
    )
    evaluated = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence(
                        "Familiar with Python",
                        "mentions Python",
                        accuracy=1.0,
                        evaluator_justification="confirmed",
                    ),
                    "seniority_level": _evidence(
                        "",
                        "not supported by text",
                        accuracy=0.2,
                        evaluator_justification=(
                            "document never states a seniority level"
                        ),
                    ),
                    "experience_years": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                },
            )
        ]
    )
    _mock_sessions(monkeypatch, [[extracted], [evaluated]])

    # Act
    result = await run_technical_skills_pipeline("Familiar with Python", "resume")

    # Assert
    assert len(result) == 1
    item = result[0]
    assert item["skill"] == "Python"
    assert item["seniority_level"] is None
    assert item["evidences"]["seniority_level"]["grounding_text"] == ""
    assert item["evidences"]["seniority_level"]["evaluator_justification"] == (
        "document never states a seniority level"
    )


async def test_synthesizer_filters_low_accuracy_skills(monkeypatch):
    # Arrange
    extracted = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence("Experience with Python", "mentions Python"),
                    "seniority_level": _evidence(),
                    "experience_years": _evidence(),
                },
            ),
            _item(
                "Kubernetes",
                {
                    "skill": _evidence("Experience with Docker", "assumed from Docker"),
                    "seniority_level": _evidence(),
                    "experience_years": _evidence(),
                },
            ),
        ]
    )
    evaluated = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence(
                        "Experience with Python",
                        "mentions Python",
                        accuracy=0.85,
                        evaluator_justification="confirmed",
                    ),
                    "seniority_level": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                    "experience_years": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                },
            ),
            _item(
                "Kubernetes",
                {
                    "skill": _evidence(
                        "Experience with Docker",
                        "assumed from Docker",
                        accuracy=0.4,
                        evaluator_justification=(
                            "document only mentions Docker, not Kubernetes"
                        ),
                    ),
                    "seniority_level": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                    "experience_years": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                },
            ),
        ]
    )
    _mock_sessions(monkeypatch, [[extracted], [evaluated]])

    # Act
    result = await run_technical_skills_pipeline(
        "Experience with Python and Docker", "resume"
    )

    # Assert
    assert len(result) == 1
    assert result[0]["skill"] == "Python"


async def test_doc_type_required_field_handling(monkeypatch):
    # Arrange - job_posting run: both extractor and evaluator carry "required".
    job_posting_extracted = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence("Must know Python", "mandatory core skill"),
                    "seniority_level": _evidence(),
                    "experience_years": _evidence(),
                    "required": _evidence(
                        "Must know Python", "stated as mandatory"
                    ),
                },
                required=True,
            )
        ]
    )
    job_posting_evaluated = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence(
                        "Must know Python",
                        "mandatory core skill",
                        accuracy=1.0,
                        evaluator_justification="confirmed",
                    ),
                    "seniority_level": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                    "experience_years": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                    "required": _evidence(
                        "Must know Python",
                        "stated as mandatory",
                        accuracy=1.0,
                        evaluator_justification="confirmed",
                    ),
                },
                required=True,
            )
        ]
    )
    _mock_sessions(monkeypatch, [[job_posting_extracted], [job_posting_evaluated]])

    # Act
    job_posting_result = await run_technical_skills_pipeline(
        "Must know Python", "job_posting"
    )

    # Assert
    assert job_posting_result[0]["required"] is True
    assert "required" in job_posting_result[0]["evidences"]

    # Arrange - resume run: no "required" anywhere in the extracted/evaluated payload.
    resume_extracted = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence("Experience with Python", "mentions Python"),
                    "seniority_level": _evidence(),
                    "experience_years": _evidence(),
                },
            )
        ]
    )
    resume_evaluated = json.dumps(
        [
            _item(
                "Python",
                {
                    "skill": _evidence(
                        "Experience with Python",
                        "mentions Python",
                        accuracy=1.0,
                        evaluator_justification="confirmed",
                    ),
                    "seniority_level": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                    "experience_years": _evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                },
            )
        ]
    )
    _mock_sessions(monkeypatch, [[resume_extracted], [resume_evaluated]])

    # Act
    resume_result = await run_technical_skills_pipeline(
        "Experience with Python", "resume"
    )

    # Assert
    assert "required" not in resume_result[0]
    assert "required" not in resume_result[0]["evidences"]


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
