"""Hybrid Generator-Evaluator orchestration for technical-skills extraction.

Pipeline (see spec `1.0_spec_init_technical_skills_agent_workflow.md`):
1. Generator (Extractor agent, `sonnet`): extracts candidate skills in a single turn,
   actively determining `seniority_level`, `experience_years` and `required`, with a
   per-field evidence object (`grounding_text`, `justification`) for every attribute.
2. Deterministic coordinator (this module, plain `asyncio`): splits the extracted
   items into batches of `EVAL_BATCH_SIZE` and fans them out concurrently.
3. Batch Evaluator agent (`haiku`): audits each batch against the source document on a
   per-field basis, assigning an independent `accuracy` to `skill`, `seniority_level`,
   `experience_years` and `required`, nullifying unsubstantiated fields or recovering
   ones the extractor missed.
4. Deterministic synthesizer (this module, pure Python): drops items whose `skill`
   accuracy is too low, nullifies secondary fields whose accuracy is too low,
   normalizes against the canonical taxonomies, enforces the `required`
   document-type rule, and serializes the clean result.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Literal

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)
from labs_agent_lib import get_agent_environment, get_agent_settings, get_logger
from pydantic import ValidationError

from ...server.resources.common_seniority_levels import normalize_seniority_level
from ...server.resources.common_technical_skills import normalize_technical_skill
from .definitions import EVALUATOR_AGENT_DEFINITION, EXTRACTOR_AGENT_DEFINITION
from .prompts import (
    build_correction_prompt,
    build_evaluator_user_prompt,
    build_extractor_user_prompt,
)
from .schemas import TechnicalSkillItem

logger = get_logger(__name__)

EVAL_BATCH_SIZE = 10
ACCURACY_THRESHOLD = 0.7

# Fields the evaluator sets independently of "skill"; only "required" is conditional
# on doc_type ("job_posting"), and simply absent (None) for "resume" items.
_SECONDARY_FIELDS = ("seniority_level", "experience_years", "required")

# Dropped from each evidence object before it's sent to the evaluator: they're not
# known yet at extraction time (accuracy defaults to -1.0, evaluator_justification to
# None), so sending them as-is would waste tokens and could confuse the evaluator.
_PRE_EVALUATION_EVIDENCE_KEYS = ("accuracy", "evaluator_justification")


def _extract_json_array(raw_text: str) -> str:
    """Pulls the JSON array out of an agent's final text, tolerating stray prose/fences."""
    text = raw_text.strip()
    if "```" in text:
        text = text.split("```")[1].removeprefix("json").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON array found in the agent's response")
    return text[start : end + 1]


async def _ask(client: ClaudeSDKClient, prompt: str) -> str:
    """Sends one query turn and concatenates the assistant's text blocks."""
    await client.query(prompt)
    text_parts = []
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            text_parts.extend(
                block.text for block in message.content if isinstance(block, TextBlock)
            )
    return "".join(text_parts)


async def _run_agent_session[T](
    agent_definition: AgentDefinition,
    initial_prompt: str,
    parse: Callable[[str], T],
    max_retries: int,
    label: str,
) -> T:
    """Runs one agent on its own `ClaudeSDKClient` session, with a self-correction
    retry loop: whenever `parse` raises a recoverable error, the agent is asked - on
    the same session - to correct its previous response.
    """
    options = ClaudeAgentOptions(
        env=get_agent_environment(get_agent_settings()).env,
        system_prompt=agent_definition.prompt,
        model=agent_definition.model,
        tools=agent_definition.tools,
    )

    attempts = max(max_retries, 0) + 1
    prompt = initial_prompt
    last_error: Exception | None = None

    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(attempts):
            raw_text = await _ask(client, prompt)
            try:
                return parse(raw_text)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "%s attempt %d/%d returned invalid output: %s",
                    label,
                    attempt + 1,
                    attempts,
                    exc,
                )
                prompt = build_correction_prompt(exc)

    raise RuntimeError(
        f"{label}: agent failed to produce valid output after {attempts} attempt(s): "
        f"{last_error}"
    )


def _parse_items(raw_text: str) -> list[TechnicalSkillItem]:
    items = json.loads(_extract_json_array(raw_text))
    return [TechnicalSkillItem.model_validate(item) for item in items]


async def _run_extractor(
    content: str, doc_type: str, max_retries: int
) -> list[TechnicalSkillItem]:
    prompt = build_extractor_user_prompt(content, doc_type)
    return await _run_agent_session(
        EXTRACTOR_AGENT_DEFINITION,
        prompt,
        _parse_items,
        max_retries,
        "extract_technical_skills[extractor]",
    )


def _parse_evaluated(raw_text: str, expected_len: int) -> list[TechnicalSkillItem]:
    parsed = _parse_items(raw_text)
    if len(parsed) != expected_len:
        raise ValueError(
            f"evaluator returned {len(parsed)} items, expected {expected_len}"
        )
    return parsed


def _strip_for_evaluator(item: TechnicalSkillItem) -> dict:
    """Dumps an extracted item for the evaluator prompt, dropping the not-yet-known
    `accuracy`/`evaluator_justification` placeholders from each evidence object.
    """
    dump = item.model_dump()
    for evidence in dump["evidences"].values():
        if evidence is not None:
            for key in _PRE_EVALUATION_EVIDENCE_KEYS:
                evidence.pop(key, None)
    return dump


async def _run_evaluator_batch(
    content: str,
    doc_type: str,
    batch: list[TechnicalSkillItem],
    max_retries: int,
) -> list[TechnicalSkillItem]:
    batch_payload = [_strip_for_evaluator(item) for item in batch]
    prompt = build_evaluator_user_prompt(content, doc_type, batch_payload)
    return await _run_agent_session(
        EVALUATOR_AGENT_DEFINITION,
        prompt,
        lambda raw_text: _parse_evaluated(raw_text, len(batch)),
        max_retries,
        "extract_technical_skills[evaluator]",
    )


def _make_batches[T](items: list[T], size: int) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def _evaluate_all(
    content: str,
    doc_type: str,
    extracted: list[TechnicalSkillItem],
    max_retries: int,
) -> list[TechnicalSkillItem]:
    """Coordinator: fans batches of up to `EVAL_BATCH_SIZE` extracted items out to
    concurrent Evaluator agent sessions via `asyncio.gather`, then flattens the
    per-batch results back into the original item order.
    """
    batches = _make_batches(extracted, EVAL_BATCH_SIZE)
    batch_results = await asyncio.gather(
        *(
            _run_evaluator_batch(content, doc_type, batch, max_retries)
            for batch in batches
        )
    )
    return [item for batch_result in batch_results for item in batch_result]


def _synthesize(doc_type: str, evaluated: list[TechnicalSkillItem]) -> list[dict]:
    """Deterministic synthesizer: drops unverified skills, nullifies unsubstantiated
    secondary fields, normalizes against the canonical taxonomies, enforces the
    `required` document-type rule, and serializes.
    """
    results = []
    for item in evaluated:
        if item.evidences.skill.accuracy < ACCURACY_THRESHOLD:
            continue

        for field in _SECONDARY_FIELDS:
            evidence = getattr(item.evidences, field)
            if evidence is None:
                continue
            if evidence.accuracy < ACCURACY_THRESHOLD:
                setattr(item, field, None)
                evidence.grounding_text = ""
            if getattr(item, field) is None:
                evidence.grounding_text = ""

        item.skill = normalize_technical_skill(item.skill) or item.skill
        if item.seniority_level is not None:
            item.seniority_level = (
                normalize_seniority_level(item.seniority_level) or item.seniority_level
            )

        dump = item.model_dump()
        if doc_type == "resume":
            dump.pop("required", None)
            dump["evidences"].pop("required", None)
        results.append(dump)
    return results


async def run_technical_skills_pipeline(
    content: str,
    doc_type: Literal["resume", "job_posting"],
    max_retries: int = 2,
) -> list[dict]:
    """Runs the full Generator-Evaluator-Synthesizer pipeline for one document.

    Args:
        content: Plain text of the resume or job posting to analyze.
        doc_type: "resume" or "job_posting".
        max_retries: Max self-correction attempts per agent session if its JSON
            output fails validation.
    """
    logger.info(
        "Running technical-skills pipeline for doc_type=%s (max_retries=%d)",
        doc_type,
        max_retries,
    )

    extracted = await _run_extractor(content, doc_type, max_retries)
    if not extracted:
        return []

    evaluated = await _evaluate_all(content, doc_type, extracted, max_retries)
    return _synthesize(doc_type, evaluated)
