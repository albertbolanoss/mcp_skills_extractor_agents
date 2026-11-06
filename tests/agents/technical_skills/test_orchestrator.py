"""Tests for the technical-skills Generator-Evaluator orchestrator internals."""

import json
from types import SimpleNamespace

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from mcp_skills_extractor_agents.agents.technical_skills import (
    orchestrator as module,
)
from mcp_skills_extractor_agents.agents.technical_skills.schemas import (
    DEFAULT_NULL_JUSTIFICATION,
    TechnicalSkillItem,
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
    """Keeps the observability writers a no-op for these orchestrator-focused tests."""

    observability_enabled = False
    prompt_log_dir = "unused"
    agent_transcript_dir = "unused"


def _mock_agent(monkeypatch, sessions: list[list[str]]) -> _FakeClientFactory:
    factory = _FakeClientFactory(sessions)
    monkeypatch.setattr(module, "ClaudeSDKClient", factory)
    monkeypatch.setattr(
        module, "get_agent_environment", lambda settings: SimpleNamespace(env={})
    )
    monkeypatch.setattr(module, "get_agent_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        module, "get_skill_agent_settings", lambda: _FakeSkillAgentSettings()
    )
    module._cached_agent_env.cache_clear()
    return factory


def _item(
    skill: str = "Python",
    seniority_level: str | None = "Senior",
    experience_years: int | None = 5,
    required: bool | None = None,
    skill_accuracy: float = 1.0,
    seniority_accuracy: float = 1.0,
    experience_accuracy: float = 1.0,
    required_accuracy: float | None = None,
) -> TechnicalSkillItem:
    """Builds a fully-evaluated TechnicalSkillItem for synthesizer/merge-helper tests."""
    evidences = {
        "skill": {
            "grounding_text": skill,
            "justification": "stated",
            "accuracy": skill_accuracy,
            "evaluator_justification": "ok",
        },
        "seniority_level": {
            "grounding_text": seniority_level or "",
            "justification": "stated",
            "accuracy": seniority_accuracy,
            "evaluator_justification": "ok",
        },
        "experience_years": {
            "grounding_text": "5 years",
            "justification": "stated",
            "accuracy": experience_accuracy,
            "evaluator_justification": "ok",
        },
    }
    if required_accuracy is not None:
        evidences["required"] = {
            "grounding_text": "required" if required else "optional",
            "justification": "stated",
            "accuracy": required_accuracy,
            "evaluator_justification": "ok",
        }
    return TechnicalSkillItem(
        skill=skill,
        seniority_level=seniority_level,
        experience_years=experience_years,
        required=required,
        evidences=evidences,
    )


# --- _extract_json_array -----------------------------------------------------------


def test_extract_json_array_strips_markdown_code_fences():
    # Arrange
    raw = '```json\n[{"skill": "Go"}]\n```'

    # Act / Assert
    assert module._extract_json_array(raw) == '[{"skill": "Go"}]'


def test_extract_json_array_raises_when_no_array_found():
    # Act / Assert
    with pytest.raises(ValueError):
        module._extract_json_array("no json here")


# --- _ask ----------------------------------------------------------------------------


async def test_ask_ignores_messages_that_are_neither_assistant_nor_result():
    # Arrange
    class _Client:
        async def query(self, prompt: str) -> None:
            return None

        async def receive_response(self):
            yield object()
            yield AssistantMessage(content=[TextBlock(text="hello")], model="sonnet")

    # Act
    text, session_id = await module._ask(_Client(), "prompt")

    # Assert
    assert text == "hello"
    assert session_id is None


# --- _batches --------------------------------------------------------------------


def test_batches_splits_into_fixed_size_chunks_with_remainder():
    # Act
    result = module._batches(list(range(25)), 10)

    # Assert
    assert [len(batch) for batch in result] == [10, 10, 5]


def test_batches_returns_empty_list_for_no_items():
    # Act / Assert
    assert module._batches([], 10) == []


# --- _cached_agent_env -------------------------------------------------------------


def test_cached_agent_env_reuses_the_same_dict_across_calls(monkeypatch):
    # Arrange
    calls = []

    def fake_get_agent_environment(settings):
        calls.append(settings)
        return SimpleNamespace(env={"X": "1"})

    monkeypatch.setattr(module, "get_agent_environment", fake_get_agent_environment)
    monkeypatch.setattr(module, "get_agent_settings", lambda: SimpleNamespace())
    module._cached_agent_env.cache_clear()

    # Act
    first = module._cached_agent_env()
    second = module._cached_agent_env()

    # Assert
    assert first == {"X": "1"}
    assert first is second
    assert len(calls) == 1


# --- _merge_evaluated_item ---------------------------------------------------------


def test_merge_evaluated_item_inherits_omitted_grounding_text_and_justification():
    # Arrange
    original = TechnicalSkillItem(
        skill="Python",
        seniority_level="Senior",
        experience_years=5,
        evidences={
            "skill": {
                "grounding_text": "Python expert",
                "justification": "stated expert",
            },
            "seniority_level": {
                "grounding_text": "Senior Engineer",
                "justification": "title",
            },
            "experience_years": {
                "grounding_text": "5 years",
                "justification": "stated",
            },
        },
    )
    raw_item = {
        "evidences": {
            "skill": {"accuracy": 1.0, "evaluator_justification": "confirmed"},
            "seniority_level": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
            "experience_years": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
        }
    }

    # Act
    merged = module._merge_evaluated_item(raw_item, original)

    # Assert
    assert merged.skill == "Python"
    assert merged.evidences.skill.grounding_text == "Python expert"
    assert merged.evidences.skill.justification == "stated expert"
    assert merged.evidences.skill.accuracy == 1.0
    assert merged.evidences.skill.evaluator_justification == "confirmed"


def test_merge_evaluated_item_applies_explicit_nullification():
    # Arrange
    original = TechnicalSkillItem(
        skill="Python",
        seniority_level="Senior",
        experience_years=5,
        evidences={
            "skill": {"grounding_text": "Python", "justification": "stated"},
            "seniority_level": {
                "grounding_text": "Senior dev",
                "justification": "title",
            },
            "experience_years": {
                "grounding_text": "5 years",
                "justification": "stated",
            },
        },
    )
    raw_item = {
        "seniority_level": None,
        "evidences": {
            "skill": {"accuracy": 1.0, "evaluator_justification": "confirmed"},
            "seniority_level": {
                "accuracy": 0.1,
                "evaluator_justification": "unsubstantiated",
                "grounding_text": "",
            },
            "experience_years": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
        },
    }

    # Act
    merged = module._merge_evaluated_item(raw_item, original)

    # Assert
    assert merged.seniority_level is None
    assert merged.evidences.seniority_level.accuracy == 0.1
    assert merged.evidences.seniority_level.grounding_text == ""
    assert merged.evidences.seniority_level.justification == "title"
    assert merged.evidences.seniority_level.evaluator_justification == "unsubstantiated"


def test_merge_evaluated_item_recovers_missed_secondary_field():
    # Arrange
    original = TechnicalSkillItem(
        skill="Python",
        seniority_level=None,
        experience_years=5,
        evidences={
            "skill": {"grounding_text": "Python", "justification": "stated"},
            "seniority_level": {
                "grounding_text": "",
                "justification": DEFAULT_NULL_JUSTIFICATION,
            },
            "experience_years": {
                "grounding_text": "5 years",
                "justification": "stated",
            },
        },
    )
    raw_item = {
        "seniority_level": "Senior",
        "evidences": {
            "skill": {"accuracy": 1.0, "evaluator_justification": "confirmed"},
            "seniority_level": {
                "accuracy": 1.0,
                "evaluator_justification": "recovered from job title",
                "grounding_text": "Senior Backend Engineer",
                "justification": "title states seniority",
            },
            "experience_years": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
        },
    }

    # Act
    merged = module._merge_evaluated_item(raw_item, original)

    # Assert
    assert merged.seniority_level == "Senior"
    assert merged.evidences.seniority_level.grounding_text == "Senior Backend Engineer"
    assert merged.evidences.seniority_level.accuracy == 1.0
    assert (
        merged.evidences.seniority_level.evaluator_justification
        == "recovered from job title"
    )


def test_merge_evaluated_item_ignores_explicit_none_values_within_an_evidence_entry():
    # Arrange
    original = TechnicalSkillItem(
        skill="Python",
        seniority_level="Senior",
        experience_years=5,
        evidences={
            "skill": {
                "grounding_text": "Python expert",
                "justification": "stated expert",
            },
            "seniority_level": {
                "grounding_text": "Senior Engineer",
                "justification": "title",
            },
            "experience_years": {
                "grounding_text": "5 years",
                "justification": "stated",
            },
        },
    )
    raw_item = {
        "evidences": {
            # grounding_text explicitly null alongside a real accuracy update: the
            # None must not clobber the inherited grounding_text, only the other key
            # applies, and the loop must keep going to the following keys/fields.
            "skill": {
                "grounding_text": None,
                "justification": None,
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
            "seniority_level": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
            "experience_years": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
        }
    }

    # Act
    merged = module._merge_evaluated_item(raw_item, original)

    # Assert
    assert merged.evidences.skill.grounding_text == "Python expert"
    assert merged.evidences.skill.justification == "stated expert"
    assert merged.evidences.skill.accuracy == 1.0


def test_merge_evaluated_item_keeps_required_evidence_none_for_resume():
    # Arrange
    original = TechnicalSkillItem(
        skill="Python",
        seniority_level="Senior",
        experience_years=5,
        required=None,
        evidences={
            "skill": {"grounding_text": "Python", "justification": "stated"},
            "seniority_level": {"grounding_text": "Senior", "justification": "title"},
            "experience_years": {
                "grounding_text": "5 years",
                "justification": "stated",
            },
        },
    )
    raw_item = {
        "evidences": {
            "skill": {"accuracy": 1.0, "evaluator_justification": "confirmed"},
            "seniority_level": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
            "experience_years": {
                "accuracy": 1.0,
                "evaluator_justification": "confirmed",
            },
        }
    }

    # Act
    merged = module._merge_evaluated_item(raw_item, original)

    # Assert
    assert merged.required is None
    assert merged.evidences.required is None


# --- _parse_evaluated --------------------------------------------------------------


def test_parse_evaluated_raises_on_length_mismatch():
    # Arrange
    original_batch = [_item()]
    raw_text = json.dumps([{}, {}])

    # Act / Assert
    with pytest.raises(ValueError):
        module._parse_evaluated(raw_text, original_batch)


def test_parse_evaluated_merges_each_item_in_order():
    # Arrange
    original_batch = [_item(skill="Python"), _item(skill="Go")]
    raw_text = json.dumps(
        [
            {
                "evidences": {
                    "skill": {"accuracy": 1.0, "evaluator_justification": "ok"}
                }
            },
            {
                "evidences": {
                    "skill": {
                        "accuracy": 0.0,
                        "evaluator_justification": "hallucinated",
                    }
                }
            },
        ]
    )

    # Act
    result = module._parse_evaluated(raw_text, original_batch)

    # Assert
    assert [item.skill for item in result] == ["Python", "Go"]
    assert result[0].evidences.skill.accuracy == 1.0
    assert result[1].evidences.skill.accuracy == 0.0


# --- _run_agent_session retry loop (via _run_extractor) ---------------------------


async def test_retry_loop_recovers_from_malformed_json(monkeypatch):
    # Arrange
    valid_json = json.dumps(
        [
            {
                "skill": "Go",
                "evidences": {
                    "skill": {
                        "grounding_text": "Go developer",
                        "justification": "stated",
                    }
                },
            }
        ]
    )
    factory = _mock_agent(monkeypatch, [["not json", valid_json]])

    # Act
    result = await module._run_extractor(
        "Go developer", "resume", max_retries=1, correlation_id="corr-1"
    )

    # Assert
    assert [item.skill for item in result] == ["Go"]
    assert len(factory.clients) == 1
    assert len(factory.clients[0].prompts) == 2


async def test_run_extractor_raises_after_exhausting_retries(monkeypatch):
    # Arrange
    _mock_agent(monkeypatch, [["still not json", "still not json"]])

    # Act / Assert
    with pytest.raises(RuntimeError):
        await module._run_extractor(
            "whatever", "resume", max_retries=1, correlation_id=""
        )


async def test_run_extractor_uses_single_turn_tool_free_options(monkeypatch):
    # Arrange
    valid_json = json.dumps(
        [
            {
                "skill": "Go",
                "evidences": {"skill": {"grounding_text": "Go", "justification": "x"}},
            }
        ]
    )
    factory = _mock_agent(monkeypatch, [[valid_json]])

    # Act
    await module._run_extractor(
        "Go developer", "resume", max_retries=0, correlation_id=""
    )

    # Assert
    options = factory.clients[0].options
    assert options.max_turns == 1
    assert options.tools == []
    assert options.model == module.EXTRACTOR_AGENT_DEFINITION.model


# --- _run_evaluator_batch ----------------------------------------------------------


async def test_run_evaluator_batch_merges_and_returns_items(monkeypatch):
    # Arrange
    original = [_item(skill="Python")]
    raw_text = json.dumps(
        [
            {
                "evidences": {
                    "skill": {"accuracy": 1.0, "evaluator_justification": "confirmed"}
                }
            }
        ]
    )
    factory = _mock_agent(monkeypatch, [[raw_text]])

    # Act
    result = await module._run_evaluator_batch(
        original,
        "Python dev",
        "resume",
        max_retries=2,
        correlation_id="corr-1",
        batch_index=0,
    )

    # Assert
    assert result[0].evidences.skill.accuracy == 1.0
    assert result[0].evidences.skill.evaluator_justification == "confirmed"
    assert factory.clients[0].options.model == module.EVALUATOR_AGENT_DEFINITION.model


# --- _synthesize ---------------------------------------------------------------------


def test_synthesizer_filters_low_accuracy_skills():
    # Arrange
    high = _item(skill="Python", skill_accuracy=0.85)
    low = _item(skill="COBOL", skill_accuracy=0.4)

    # Act
    result = module._synthesize([high, low], "resume")

    # Assert
    assert [item["skill"] for item in result] == ["Python"]


def test_synthesizer_nullifies_low_accuracy_secondary_field_and_blanks_grounding_text():
    # Arrange
    item = _item(
        skill="Python",
        skill_accuracy=1.0,
        seniority_level="Senior",
        seniority_accuracy=0.2,
    )
    item.evidences.seniority_level.grounding_text = "Senior Developer"
    item.evidences.seniority_level.evaluator_justification = "unsubstantiated title"

    # Act
    [result] = module._synthesize([item], "resume")

    # Assert
    assert result["seniority_level"] is None
    assert result["evidences"]["seniority_level"]["grounding_text"] == ""
    assert (
        result["evidences"]["seniority_level"]["evaluator_justification"]
        == "unsubstantiated title"
    )


def test_synthesizer_blanks_grounding_text_for_legitimate_abstention():
    # Arrange
    item = _item(skill="Python", seniority_level=None, seniority_accuracy=1.0)
    item.evidences.seniority_level.grounding_text = ""

    # Act
    [result] = module._synthesize([item], "resume")

    # Assert
    assert result["seniority_level"] is None
    assert result["evidences"]["seniority_level"]["grounding_text"] == ""
    assert result["evidences"]["seniority_level"]["accuracy"] == 1.0


def test_synthesizer_normalizes_skill_and_seniority_level():
    # Arrange
    item = _item(skill="Postgres", seniority_level="Sr")

    # Act
    [result] = module._synthesize([item], "resume")

    # Assert
    assert result["skill"] == "PostgreSQL"
    assert result["seniority_level"] == "Senior"


def test_synthesizer_omits_required_for_resume():
    # Arrange
    item = _item(required=True, required_accuracy=1.0)

    # Act
    [result] = module._synthesize([item], "resume")

    # Assert
    assert "required" not in result
    assert "required" not in result["evidences"]


def test_synthesizer_keeps_required_for_job_posting():
    # Arrange
    item = _item(required=True, required_accuracy=1.0)

    # Act
    [result] = module._synthesize([item], "job_posting")

    # Assert
    assert result["required"] is True
    assert result["evidences"]["required"]["accuracy"] == 1.0
