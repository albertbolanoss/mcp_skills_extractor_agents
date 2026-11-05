"""Tests for orchestrator.py's pure helpers and the agent-session retry loop."""

import json
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock

from mcp_skills_extractor_agents.agents.technical_skills import orchestrator as module
from mcp_skills_extractor_agents.agents.technical_skills.orchestrator import (
    _extract_json_array,
    _make_batches,
    run_technical_skills_pipeline,
)
from mcp_skills_extractor_agents.agents.technical_skills.schemas import (
    FieldEvidence,
    SkillEvidences,
    TechnicalSkillItem,
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


def _abstained_evidence(justification: str = "not stated", **extra) -> dict:
    """Builds a FieldEvidence-shaped dict for a field the extractor left undetermined."""
    return {"grounding_text": "", "justification": justification, **extra}


def test_extract_json_array_strips_markdown_code_fences():
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
                "evidences": {
                    "skill": {
                        "grounding_text": "Python experience",
                        "justification": "mentions Python",
                    },
                    "seniority_level": _abstained_evidence(),
                    "experience_years": _abstained_evidence(),
                },
            }
        ]
    )
    mismatched = json.dumps([])  # 0 items, expected 1 -> triggers a correction retry
    corrected = json.dumps(
        [
            {
                "skill": "Python",
                "evidences": {
                    "skill": {
                        "grounding_text": "Python experience",
                        "justification": "mentions Python",
                        "accuracy": 1.0,
                        "evaluator_justification": "confirmed",
                    },
                    "seniority_level": _abstained_evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                    "experience_years": _abstained_evidence(
                        accuracy=1.0, evaluator_justification="confirmed abstention"
                    ),
                },
            }
        ]
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
            "seniority_level": None,
            "experience_years": None,
            "evidences": {
                "skill": {
                    "grounding_text": "Python experience",
                    "justification": "mentions Python",
                    "evaluator_justification": "confirmed",
                    "accuracy": 1.0,
                },
                "seniority_level": {
                    "grounding_text": "",
                    "justification": "not stated",
                    "evaluator_justification": "confirmed abstention",
                    "accuracy": 1.0,
                },
                "experience_years": {
                    "grounding_text": "",
                    "justification": "not stated",
                    "evaluator_justification": "confirmed abstention",
                    "accuracy": 1.0,
                },
            },
        }
    ]


def test_make_batches_splits_into_chunks_of_size():
    # Act
    result = _make_batches(list(range(7)), 3)

    # Assert
    assert result == [[0, 1, 2], [3, 4, 5], [6]]


def test_strip_for_evaluator_drops_unevaluated_keys_for_resume_item():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Experience with Python", justification="mentions Python"
            ),
            seniority_level=FieldEvidence(justification="not stated"),
            experience_years=FieldEvidence(justification="not stated"),
        ),
    )

    # Act
    stripped = module._strip_for_evaluator(item)

    # Assert
    assert stripped["evidences"]["required"] is None
    for field in ("skill", "seniority_level", "experience_years"):
        assert "accuracy" not in stripped["evidences"][field]
        assert "evaluator_justification" not in stripped["evidences"][field]


def test_strip_for_evaluator_drops_required_evidence_keys_for_job_posting_item():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        required=True,
        evidences=SkillEvidences(
            skill=FieldEvidence(grounding_text="Python", justification="mentions Python"),
            seniority_level=FieldEvidence(justification="not stated"),
            experience_years=FieldEvidence(justification="not stated"),
            required=FieldEvidence(
                grounding_text="Must know Python", justification="mandatory"
            ),
        ),
    )

    # Act
    stripped = module._strip_for_evaluator(item)

    # Assert
    assert "accuracy" not in stripped["evidences"]["required"]
    assert "evaluator_justification" not in stripped["evidences"]["required"]


def test_synthesize_filters_item_with_low_skill_accuracy():
    # Arrange
    kept = TechnicalSkillItem(
        skill="Python",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Experience with Python",
                justification="mentions Python",
                accuracy=0.85,
                evaluator_justification="confirmed",
            ),
            seniority_level=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
            experience_years=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
        ),
    )
    dropped = TechnicalSkillItem(
        skill="Kubernetes",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Experience with Docker",
                justification="assumed from Docker",
                accuracy=0.4,
                evaluator_justification="document only mentions Docker",
            ),
            seniority_level=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
            experience_years=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
        ),
    )

    # Act
    result = module._synthesize("resume", [kept, dropped])

    # Assert
    assert len(result) == 1
    assert result[0]["skill"] == "Python"


def test_synthesize_nullifies_secondary_field_with_low_accuracy():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        seniority_level="Senior",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Familiar with Python",
                justification="mentions Python",
                accuracy=1.0,
                evaluator_justification="confirmed",
            ),
            seniority_level=FieldEvidence(
                grounding_text="Familiar with Python",
                justification="guessed from the skill alone",
                accuracy=0.2,
                evaluator_justification="not supported by text",
            ),
            experience_years=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
        ),
    )

    # Act
    result = module._synthesize("resume", [item])

    # Assert
    assert result[0]["seniority_level"] is None
    assert result[0]["evidences"]["seniority_level"]["grounding_text"] == ""
    assert (
        result[0]["evidences"]["seniority_level"]["evaluator_justification"]
        == "not supported by text"
    )


def test_synthesize_preserves_correct_abstention():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Skills: Python, Docker",
                justification="listed in skills section",
                accuracy=1.0,
                evaluator_justification="confirmed present",
            ),
            seniority_level=FieldEvidence(
                justification=(
                    "Listed only in skills section without proficiency descriptor "
                    "or date range."
                ),
                accuracy=1.0,
                evaluator_justification="confirmed abstention: no descriptor in text",
            ),
            experience_years=FieldEvidence(
                justification=(
                    "Listed only in skills section without proficiency descriptor "
                    "or date range."
                ),
                accuracy=1.0,
                evaluator_justification="confirmed abstention: no date range in text",
            ),
        ),
    )

    # Act
    result = module._synthesize("resume", [item])

    # Assert
    assert result[0]["seniority_level"] is None
    assert result[0]["evidences"]["seniority_level"]["grounding_text"] == ""
    assert result[0]["evidences"]["seniority_level"]["accuracy"] == 1.0


def test_synthesize_keeps_evaluator_recovered_secondary_field():
    # Arrange
    item = TechnicalSkillItem(
        skill="Apache Kafka",
        seniority_level="Senior",
        experience_years=4,
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Architected event-driven pipelines using Apache Kafka",
                justification="explicit mention",
                accuracy=1.0,
                evaluator_justification="confirmed",
            ),
            seniority_level=FieldEvidence(
                grounding_text="Senior Backend Engineer (2021 - 2025)",
                justification="role title recovered by evaluator",
                accuracy=1.0,
                evaluator_justification=(
                    "extractor missed the role title; recovered Senior from it"
                ),
            ),
            experience_years=FieldEvidence(
                grounding_text="Senior Backend Engineer (2021 - 2025)",
                justification="2021-2025 recovered by evaluator",
                accuracy=1.0,
                evaluator_justification=(
                    "extractor missed the date range; recovered 4 years from it"
                ),
            ),
        ),
    )

    # Act
    result = module._synthesize("resume", [item])

    # Assert
    assert result[0]["seniority_level"] == "Senior"
    assert result[0]["experience_years"] == 4
    assert result[0]["evidences"]["seniority_level"][
        "evaluator_justification"
    ].startswith("extractor missed")


def test_synthesize_normalizes_skill_and_seniority_level_aliases():
    # Arrange
    item = TechnicalSkillItem(
        skill="JS",
        seniority_level="Sr",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Senior JS engineer",
                justification="title",
                accuracy=1.0,
                evaluator_justification="confirmed",
            ),
            seniority_level=FieldEvidence(
                grounding_text="Senior JS engineer",
                justification="title",
                accuracy=1.0,
                evaluator_justification="confirmed",
            ),
            experience_years=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
        ),
    )

    # Act
    result = module._synthesize("resume", [item])

    # Assert
    assert result[0]["skill"] == "JavaScript"
    assert result[0]["seniority_level"] == "Senior"


def test_synthesize_includes_required_for_job_posting():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        required=True,
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Must know Python",
                justification="mandatory",
                accuracy=1.0,
                evaluator_justification="confirmed",
            ),
            seniority_level=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
            experience_years=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
            required=FieldEvidence(
                grounding_text="Must know Python",
                justification="mandatory",
                accuracy=1.0,
                evaluator_justification="confirmed",
            ),
        ),
    )

    # Act
    result = module._synthesize("job_posting", [item])

    # Assert
    assert result[0]["required"] is True
    assert result[0]["evidences"]["required"]["accuracy"] == 1.0


def test_synthesize_omits_required_for_resume():
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        evidences=SkillEvidences(
            skill=FieldEvidence(
                grounding_text="Python",
                justification="mentions Python",
                accuracy=1.0,
                evaluator_justification="confirmed",
            ),
            seniority_level=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
            experience_years=FieldEvidence(
                justification="not stated",
                accuracy=1.0,
                evaluator_justification="confirmed abstention",
            ),
        ),
    )

    # Act
    result = module._synthesize("resume", [item])

    # Assert
    assert "required" not in result[0]
    assert "required" not in result[0]["evidences"]
