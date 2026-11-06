"""Hybrid Generator-Evaluator orchestration for evidence-grounded technical-skill
extraction: `run_technical_skills_pipeline` is the single entrypoint the MCP tool
wrapper (`server/tools/technical_skill_extraction.py`) delegates to.

Pipeline stages:
1. Generator - `_run_extractor` runs a single-turn `sonnet`-class extraction, with the
   same self-correction retry loop every extraction tool in this project uses.
2. Deterministic Coordinator - `run_technical_skills_pipeline` short-circuits to `[]`
   immediately when the Extractor finds nothing (no Evaluator call at all), otherwise
   splits the extracted items into `EVAL_BATCH_SIZE`-sized batches and evaluates every
   batch concurrently via `asyncio.gather`.
3. Batch Evaluator - `_run_evaluator_batch` runs a single-turn `haiku`-class audit per
   batch; `_merge_evaluated_item` then deterministically merges whatever delta the
   Evaluator returned back onto the Extractor's original item, so the Evaluator never
   has to re-emit unchanged `grounding_text`/`justification` strings to save tokens.
4. Deterministic Synthesizer - `_synthesize` filters out unsubstantiated skills,
   nullifies unsubstantiated secondary fields, normalizes against the canonical
   taxonomies, and applies the resume/job_posting field-presence rules.
"""

import asyncio
import json
from collections.abc import Callable
from functools import lru_cache
from typing import Literal

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)
from labs_agent_lib import get_agent_environment, get_agent_settings, get_logger
from pydantic import ValidationError

from ...observability import ToolObservability
from ...server.resources.common_seniority_levels import normalize_seniority_level
from ...server.resources.common_technical_skills import normalize_technical_skill
from ...settings import get_skill_agent_settings
from .definitions import EVALUATOR_AGENT_DEFINITION, EXTRACTOR_AGENT_DEFINITION
from .prompts import (
    EVALUATOR_CORRECTION_PROMPT,
    EXTRACTOR_CORRECTION_PROMPT,
    build_evaluator_user_prompt,
    build_extractor_user_prompt,
)
from .schemas import TechnicalSkillItem

logger = get_logger(__name__)

EVAL_BATCH_SIZE = 10
ACCURACY_THRESHOLD = 0.7


@lru_cache(maxsize=1)
def _cached_agent_env() -> dict[str, str]:
    """Caches the Claude Agent SDK environment for the process so that N concurrent
    evaluator batches don't each reconstruct it from settings."""
    return get_agent_environment(get_agent_settings()).env


def _agent_options(agent_definition: AgentDefinition) -> ClaudeAgentOptions:
    """Builds single-turn, tool-free ClaudeAgentOptions for one agent definition."""
    return ClaudeAgentOptions(
        env=_cached_agent_env(),
        system_prompt=agent_definition.prompt,
        model=agent_definition.model,
        tools=agent_definition.tools or [],
        max_turns=1,
    )


def _observability_for(
    tool_name: str, correlation_id: str, agent_definition: AgentDefinition
) -> ToolObservability:
    return ToolObservability(
        get_skill_agent_settings(),
        tool_name=tool_name,
        correlation_id=correlation_id,
        model=agent_definition.model,
        system_prompt=agent_definition.prompt,
    )


def _dump_items(items: list[TechnicalSkillItem]) -> list[dict]:
    return [item.model_dump() for item in items]


def _extract_json_array(raw_text: str) -> str:
    """Pulls the JSON array out of the agent's final text, tolerating stray prose/fences."""
    text = raw_text.strip()
    if "```" in text:
        text = text.split("```")[1].removeprefix("json").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON array found in the agent's response")
    return text[start : end + 1]


async def _ask(client: ClaudeSDKClient, prompt: str) -> tuple[str, str | None]:
    """Sends `prompt` and drains the response, returning `(text, session_id)`."""
    await client.query(prompt)
    text_parts = []
    session_id: str | None = None
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            text_parts.extend(
                block.text for block in message.content if isinstance(block, TextBlock)
            )
        elif isinstance(message, ResultMessage):
            session_id = message.session_id
    return "".join(text_parts), session_id


def _parse_extracted(raw_text: str) -> list[TechnicalSkillItem]:
    """Validates the Extractor's raw text against `TechnicalSkillItem`."""
    items = json.loads(_extract_json_array(raw_text))
    return [TechnicalSkillItem.model_validate(item) for item in items]


def _merge_evaluated_item(
    raw_item: dict, original: TechnicalSkillItem
) -> TechnicalSkillItem:
    """Merges Evaluator delta/output with Extractor's original item before Pydantic validation."""
    merged = {
        "skill": raw_item.get("skill", original.skill),
        "seniority_level": raw_item.get("seniority_level", original.seniority_level),
        "experience_years": raw_item.get("experience_years", original.experience_years),
        "required": raw_item.get("required", original.required),
    }
    orig_ev_dump = original.evidences.model_dump()
    raw_evidences = raw_item.get("evidences") or {}
    merged_evidences: dict = {}

    for field_name, orig_field_ev in orig_ev_dump.items():
        raw_field_ev = raw_evidences.get(field_name)
        if orig_field_ev is None and raw_field_ev is None:
            merged_evidences[field_name] = None
            continue
        base_ev = dict(orig_field_ev or {})
        if isinstance(raw_field_ev, dict):
            for k, v in raw_field_ev.items():
                if v is not None:
                    base_ev[k] = v
        merged_evidences[field_name] = base_ev

    merged["evidences"] = merged_evidences
    return TechnicalSkillItem.model_validate(merged)


def _parse_evaluated(
    raw_text: str, original_batch: list[TechnicalSkillItem]
) -> list[TechnicalSkillItem]:
    """Validates the Evaluator's raw text and delta-merges it onto `original_batch`."""
    raw_items = json.loads(_extract_json_array(raw_text))
    if len(raw_items) != len(original_batch):
        raise ValueError(
            f"Evaluator returned {len(raw_items)} item(s), expected {len(original_batch)}"
        )
    return [
        _merge_evaluated_item(raw_item, original)
        for raw_item, original in zip(raw_items, original_batch, strict=True)
    ]


async def _run_agent_session(
    *,
    agent_definition: AgentDefinition,
    observability: ToolObservability,
    initial_prompt: str,
    correction_prompt: str,
    parse: Callable[[str], list[TechnicalSkillItem]],
    max_retries: int,
    failure_label: str,
) -> list[TechnicalSkillItem]:
    """Runs one self-correcting Claude Agent SDK session.

    Sends `initial_prompt`, and on a `parse` failure feeds the error back as a
    correction prompt on the *same* session for up to `max_retries` further attempts,
    mirroring every extraction tool's retry loop in this project. Raises RuntimeError
    once every attempt is exhausted.
    """
    options = _agent_options(agent_definition)
    attempts = max(max_retries, 0) + 1
    prompt = initial_prompt
    last_error: Exception | None = None

    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(attempts):
            observability.log_attempt_prompt(prompt=prompt, attempt=attempt + 1)
            raw_text, session_id = await _ask(client, prompt)
            observability.log_attempt_response(text=raw_text, session_id=session_id)
            try:
                result = parse(raw_text)
                observability.log_success(result=_dump_items(result))
                return result
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "%s attempt %d/%d returned invalid output: %s",
                    failure_label,
                    attempt + 1,
                    attempts,
                    exc,
                )
                prompt = correction_prompt.format(error=exc)
                observability.log_retry(
                    attempt=attempt + 1, attempts=attempts, error=str(exc)
                )

    observability.log_failure(error=str(last_error))
    raise RuntimeError(
        f"{failure_label}: agent failed to produce valid JSON after "
        f"{attempts} attempt(s): {last_error}"
    )


async def _run_extractor(
    content: str, doc_type: str, max_retries: int, correlation_id: str
) -> list[TechnicalSkillItem]:
    """Generator stage: one single-turn extraction, with self-correction retries."""
    return await _run_agent_session(
        agent_definition=EXTRACTOR_AGENT_DEFINITION,
        observability=_observability_for(
            "extract_technical_skills.extractor",
            correlation_id,
            EXTRACTOR_AGENT_DEFINITION,
        ),
        initial_prompt=build_extractor_user_prompt(content, doc_type),
        correction_prompt=EXTRACTOR_CORRECTION_PROMPT,
        parse=_parse_extracted,
        max_retries=max_retries,
        failure_label="extract_technical_skills.extractor",
    )


async def _run_evaluator_batch(
    batch: list[TechnicalSkillItem],
    content: str,
    doc_type: str,
    max_retries: int,
    correlation_id: str,
    batch_index: int,
) -> list[TechnicalSkillItem]:
    """Evaluator stage for one batch: audits every field, then delta-merges the result
    back onto `batch`'s original evidence (see `_merge_evaluated_item`)."""
    return await _run_agent_session(
        agent_definition=EVALUATOR_AGENT_DEFINITION,
        observability=_observability_for(
            f"extract_technical_skills.evaluator.batch{batch_index}",
            correlation_id,
            EVALUATOR_AGENT_DEFINITION,
        ),
        initial_prompt=build_evaluator_user_prompt(batch, content, doc_type),
        correction_prompt=EVALUATOR_CORRECTION_PROMPT,
        parse=lambda raw_text: _parse_evaluated(raw_text, batch),
        max_retries=max_retries,
        failure_label="extract_technical_skills.evaluator",
    )


def _batches(
    items: list[TechnicalSkillItem], size: int
) -> list[list[TechnicalSkillItem]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _synthesize(items: list[TechnicalSkillItem], doc_type: str) -> list[dict]:
    """Deterministic Synthesizer: filters, nullifies, normalizes and serializes."""
    results: list[dict] = []
    for item in items:
        if item.evidences.skill.accuracy < ACCURACY_THRESHOLD:
            continue

        for field_name in ("seniority_level", "experience_years", "required"):
            field_evidence = getattr(item.evidences, field_name)
            if field_evidence is None:
                continue
            if field_evidence.accuracy < ACCURACY_THRESHOLD:
                setattr(item, field_name, None)
                field_evidence.grounding_text = ""
            if getattr(item, field_name) is None:
                field_evidence.grounding_text = ""

        item.skill = normalize_technical_skill(item.skill) or item.skill
        if item.seniority_level is not None:
            item.seniority_level = (
                normalize_seniority_level(item.seniority_level) or item.seniority_level
            )

        dumped = item.model_dump()
        if doc_type != "job_posting":
            dumped.pop("required", None)
            dumped["evidences"].pop("required", None)
        results.append(dumped)
    return results


async def run_technical_skills_pipeline(
    content: str,
    doc_type: Literal["resume", "job_posting"],
    max_retries: int = 2,
    correlation_id: str = "",
) -> list[dict]:
    """
    Runs the full evidence-grounded technical-skills pipeline.

    A single-turn Extractor (sonnet) pass short-circuits to `[]` immediately if it
    finds nothing; otherwise every batch of up to `EVAL_BATCH_SIZE` extracted items is
    independently audited by a concurrent Evaluator (haiku) pass via `asyncio.gather`,
    and the deterministic Synthesizer then drops unsubstantiated skills, nullifies
    unsubstantiated secondary fields, normalizes against the canonical taxonomies, and
    applies the resume/job_posting field-presence rules.

    Args:
        content: Plain text of the resume or job posting to analyze.
        doc_type: "resume" or "job_posting".
        max_retries: Max self-correction attempts per agent session (the Extractor,
            and independently each Evaluator batch) if its JSON output fails validation.
        correlation_id: Cross-service id propagated by the coordinator so this call's
            prompt-log/transcript entries can be joined with the coordinator's own run.
            Empty when the caller doesn't provide one (e.g. manual MCP Inspector calls).
    """
    logger.info(
        "Running technical-skills pipeline for doc_type=%s (max_retries=%d)",
        doc_type,
        max_retries,
    )

    extracted = await _run_extractor(content, doc_type, max_retries, correlation_id)
    if not extracted:
        return []

    evaluated_batches = await asyncio.gather(
        *(
            _run_evaluator_batch(
                batch, content, doc_type, max_retries, correlation_id, index
            )
            for index, batch in enumerate(_batches(extracted, EVAL_BATCH_SIZE))
        )
    )
    evaluated = [item for batch in evaluated_batches for item in batch]
    return _synthesize(evaluated, doc_type)
