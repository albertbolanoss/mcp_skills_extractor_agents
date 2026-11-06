"""Tests for the technical-skills evidence-grounded extraction pipeline end-to-end."""

import ast
import asyncio
import inspect
import json
from types import SimpleNamespace

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from mcp_skills_extractor_agents.agents.technical_skills import (
    orchestrator,
    run_technical_skills_pipeline,
)
from mcp_skills_extractor_agents.agents.technical_skills.schemas import (
    DEFAULT_NULL_JUSTIFICATION,
    FieldEvidence,
    TechnicalSkillItem,
)
from mcp_skills_extractor_agents.server.tools import (
    technical_skill_extraction as tool_module,
)


class _FakeClient:
    """Fakes ClaudeSDKClient: replays one session's queued agent text responses, one
    per query() call."""

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
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-fake",
        )


class _FakeClientFactory:
    """Constructs one `_FakeClient` per `ClaudeSDKClient(options=...)` call, consuming
    queued per-session response lists in construction order (one list per agent
    session - the Extractor first, then each Evaluator batch in dispatch order)."""

    def __init__(self, sessions: list[list[str]]):
        self._sessions = iter(sessions)
        self.clients: list[_FakeClient] = []

    def __call__(self, options=None):
        client = _FakeClient(next(self._sessions), options=options)
        self.clients.append(client)
        return client


class _FakeSkillAgentSettings:
    """Keeps the observability writers a no-op for these pipeline-focused tests."""

    observability_enabled = False
    prompt_log_dir = "unused"
    agent_transcript_dir = "unused"


def _mock_agent(monkeypatch, sessions: list[list[str]]) -> _FakeClientFactory:
    factory = _FakeClientFactory(sessions)
    monkeypatch.setattr(orchestrator, "ClaudeSDKClient", factory)
    monkeypatch.setattr(
        orchestrator, "get_agent_environment", lambda settings: SimpleNamespace(env={})
    )
    monkeypatch.setattr(orchestrator, "get_agent_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        orchestrator, "get_skill_agent_settings", lambda: _FakeSkillAgentSettings()
    )
    orchestrator._cached_agent_env.cache_clear()
    return factory


def _minimal_item(skill: str) -> TechnicalSkillItem:
    return TechnicalSkillItem(
        skill=skill,
        evidences={
            "skill": {
                "grounding_text": skill,
                "justification": "stated",
                "accuracy": 1.0,
            }
        },
    )


# --- test_module_separation ---------------------------------------------------------


def test_module_separation():
    # Act
    tree = ast.parse(inspect.getsource(tool_module))
    top_level_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    imported_names = {
        alias.asname or alias.name
        for node in ast.walk(top_level_defs[0])
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    # Assert: exactly one function defined - the @mcp.tool() wrapper itself.
    assert [node.name for node in top_level_defs] == ["extract_technical_skills"]
    # Assert: it delegates to (imports) run_technical_skills_pipeline rather than
    # reimplementing the pipeline - see orchestrator.py for the real logic.
    assert "run_technical_skills_pipeline" in imported_names
    assert run_technical_skills_pipeline is orchestrator.run_technical_skills_pipeline


# --- test_field_level_evidences_structure -------------------------------------------


def test_field_level_evidences_structure_hydrates_null_secondary_attributes():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        seniority_level=None,
        experience_years=None,
        evidences={"skill": {"grounding_text": "Python", "justification": "stated"}},
    )

    # Assert
    assert item.evidences.seniority_level.grounding_text == ""
    assert item.evidences.seniority_level.justification == DEFAULT_NULL_JUSTIFICATION
    assert item.evidences.experience_years.grounding_text == ""
    assert item.evidences.experience_years.justification == DEFAULT_NULL_JUSTIFICATION
    assert item.evidences.required is None


def test_field_level_evidences_structure_accepts_required_evidence_for_job_posting():
    # Act
    item = TechnicalSkillItem(
        skill="Python",
        required=True,
        evidences={
            "skill": {"grounding_text": "Python", "justification": "stated"},
            "required": {
                "grounding_text": "must know Python",
                "justification": "mandatory",
            },
        },
    )

    # Assert
    assert isinstance(item.evidences.required, FieldEvidence)
    assert item.evidences.required.grounding_text == "must know Python"


# --- test_empty_extraction_short_circuits_evaluator ---------------------------------


async def test_empty_extraction_short_circuits_evaluator(monkeypatch):
    # Arrange
    async def fake_run_extractor(*args, **kwargs):
        return []

    calls = []

    async def fake_run_evaluator_batch(*args, **kwargs):
        calls.append(args)
        return []

    monkeypatch.setattr(orchestrator, "_run_extractor", fake_run_extractor)
    monkeypatch.setattr(orchestrator, "_run_evaluator_batch", fake_run_evaluator_batch)

    # Act
    result = await run_technical_skills_pipeline("no skills here", "resume")

    # Assert
    assert result == []
    assert calls == []


# --- test_batch_evaluation_concurrency ----------------------------------------------


async def test_batch_evaluation_concurrency(monkeypatch):
    # Arrange
    extracted_items = [_minimal_item(f"Skill{i}") for i in range(25)]

    async def fake_run_extractor(*args, **kwargs):
        return extracted_items

    batch_calls = []

    async def fake_run_evaluator_batch(
        batch, content, doc_type, max_retries, correlation_id, batch_index, report_progress=None
    ):
        batch_calls.append(list(batch))
        return batch

    gather_sizes = []
    real_gather = asyncio.gather

    async def spy_gather(*aws, **kwargs):
        gather_sizes.append(len(aws))
        return await real_gather(*aws, **kwargs)

    monkeypatch.setattr(orchestrator, "_run_extractor", fake_run_extractor)
    monkeypatch.setattr(orchestrator, "_run_evaluator_batch", fake_run_evaluator_batch)
    monkeypatch.setattr(orchestrator.asyncio, "gather", spy_gather)

    # Act
    await run_technical_skills_pipeline("25 skills", "resume")

    # Assert
    assert gather_sizes == [3]
    assert [len(batch) for batch in batch_calls] == [10, 10, 5]


# --- test_evaluator_nullifies_unsupported_secondary_field ---------------------------


async def test_evaluator_nullifies_unsupported_secondary_field(monkeypatch):
    # Arrange
    extracted_item = TechnicalSkillItem(
        skill="Python",
        seniority_level="Senior",
        experience_years=5,
        evidences={
            "skill": {"grounding_text": "Python", "justification": "stated"},
            "seniority_level": {
                "grounding_text": "Senior-sounding text",
                "justification": "guessed",
            },
            "experience_years": {
                "grounding_text": "5 years",
                "justification": "stated",
            },
        },
    )

    async def fake_run_extractor(*args, **kwargs):
        return [extracted_item]

    async def fake_run_evaluator_batch(batch, *args, **kwargs):
        item = batch[0]
        item.evidences.skill.accuracy = 1.0
        item.evidences.skill.evaluator_justification = "confirmed"
        item.evidences.seniority_level.accuracy = 0.2
        item.evidences.seniority_level.evaluator_justification = "unsubstantiated guess"
        item.evidences.experience_years.accuracy = 1.0
        item.evidences.experience_years.evaluator_justification = "confirmed"
        return [item]

    monkeypatch.setattr(orchestrator, "_run_extractor", fake_run_extractor)
    monkeypatch.setattr(orchestrator, "_run_evaluator_batch", fake_run_evaluator_batch)

    # Act
    [result] = await run_technical_skills_pipeline("resume text", "resume")

    # Assert
    assert result["skill"] == "Python"
    assert result["seniority_level"] is None
    assert result["evidences"]["seniority_level"]["grounding_text"] == ""
    assert (
        result["evidences"]["seniority_level"]["evaluator_justification"]
        == "unsubstantiated guess"
    )
    assert result["experience_years"] == 5


# --- test_doc_type_required_field_handling ------------------------------------------


async def test_doc_type_required_field_handling_resume_omits_required(monkeypatch):
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        evidences={
            "skill": {
                "grounding_text": "Python",
                "justification": "stated",
                "accuracy": 1.0,
            }
        },
    )

    async def fake_run_extractor(*args, **kwargs):
        return [item]

    async def fake_run_evaluator_batch(batch, *args, **kwargs):
        return batch

    monkeypatch.setattr(orchestrator, "_run_extractor", fake_run_extractor)
    monkeypatch.setattr(orchestrator, "_run_evaluator_batch", fake_run_evaluator_batch)

    # Act
    [result] = await run_technical_skills_pipeline("resume text", "resume")

    # Assert
    assert "required" not in result
    assert "required" not in result["evidences"]


async def test_doc_type_required_field_handling_job_posting_includes_required(
    monkeypatch,
):
    # Arrange
    item = TechnicalSkillItem(
        skill="Python",
        required=True,
        evidences={
            "skill": {
                "grounding_text": "Python",
                "justification": "stated",
                "accuracy": 1.0,
            },
            "required": {
                "grounding_text": "must know Python",
                "justification": "mandatory",
                "accuracy": 1.0,
            },
        },
    )

    async def fake_run_extractor(*args, **kwargs):
        return [item]

    async def fake_run_evaluator_batch(batch, *args, **kwargs):
        return batch

    monkeypatch.setattr(orchestrator, "_run_extractor", fake_run_extractor)
    monkeypatch.setattr(orchestrator, "_run_evaluator_batch", fake_run_evaluator_batch)

    # Act
    [result] = await run_technical_skills_pipeline("job posting text", "job_posting")

    # Assert
    assert result["required"] is True
    assert result["evidences"]["required"]["accuracy"] == 1.0


# --- report_progress threading -------------------------------------------------------


async def test_pipeline_forwards_report_progress_to_extractor_and_evaluator_batches(
    monkeypatch,
):
    # Arrange
    extracted_items = [_minimal_item("Python")]
    received = {"extractor": None, "evaluator": None}

    async def fake_run_extractor(*args, report_progress=None, **kwargs):
        received["extractor"] = report_progress
        return extracted_items

    async def fake_run_evaluator_batch(*args, report_progress=None, **kwargs):
        received["evaluator"] = report_progress
        return args[0]

    monkeypatch.setattr(orchestrator, "_run_extractor", fake_run_extractor)
    monkeypatch.setattr(orchestrator, "_run_evaluator_batch", fake_run_evaluator_batch)

    async def report_progress(message: str) -> None:
        return None

    # Act
    await run_technical_skills_pipeline(
        "resume text", "resume", report_progress=report_progress
    )

    # Assert
    assert received["extractor"] is report_progress
    assert received["evaluator"] is report_progress


# --- full pipeline, end-to-end through real (faked-client) agent sessions ----------


async def test_run_technical_skills_pipeline_end_to_end_chronological_derivation(
    monkeypatch,
):
    # Arrange
    document = (
        "Senior Backend Engineer (2021 - 2025) - Architected event-driven pipelines "
        "using Apache Kafka"
    )
    extractor_json = json.dumps(
        [
            {
                "skill": "Apache Kafka",
                "seniority_level": "Senior",
                "experience_years": 4,
                "evidences": {
                    "skill": {
                        "grounding_text": document,
                        "justification": "explicitly named in role description",
                    },
                    "seniority_level": {
                        "grounding_text": "Senior Backend Engineer (2021 - 2025)",
                        "justification": "explicit Senior title",
                    },
                    "experience_years": {
                        "grounding_text": "Senior Backend Engineer (2021 - 2025)",
                        "justification": "2021-2025 role duration equals 4 years",
                    },
                },
            }
        ]
    )
    evaluator_json = json.dumps(
        [
            {
                "evidences": {
                    "skill": {
                        "accuracy": 1.0,
                        "evaluator_justification": "present and grounded",
                    },
                    "seniority_level": {
                        "accuracy": 1.0,
                        "evaluator_justification": "title confirms Senior",
                    },
                    "experience_years": {
                        "accuracy": 1.0,
                        "evaluator_justification": "date math confirmed",
                    },
                }
            }
        ]
    )
    factory = _mock_agent(monkeypatch, [[extractor_json], [evaluator_json]])

    # Act
    result = await run_technical_skills_pipeline(document, "resume")

    # Assert
    assert result == [
        {
            "skill": "Apache Kafka",
            "seniority_level": "Senior",
            "experience_years": 4,
            "evidences": {
                "skill": {
                    "grounding_text": document,
                    "justification": "explicitly named in role description",
                    "evaluator_justification": "present and grounded",
                    "accuracy": 1.0,
                },
                "seniority_level": {
                    "grounding_text": "Senior Backend Engineer (2021 - 2025)",
                    "justification": "explicit Senior title",
                    "evaluator_justification": "title confirms Senior",
                    "accuracy": 1.0,
                },
                "experience_years": {
                    "grounding_text": "Senior Backend Engineer (2021 - 2025)",
                    "justification": "2021-2025 role duration equals 4 years",
                    "evaluator_justification": "date math confirmed",
                    "accuracy": 1.0,
                },
            },
        }
    ]
    assert len(factory.clients) == 2
