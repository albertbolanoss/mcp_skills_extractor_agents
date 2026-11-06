"""MCP tool for resume/job-posting extraction: Soft Skills.

A Claude Agent SDK agent extracts soft skills (with seniority level and years of
experience) from free-text resume/job-posting content, grounded in the project's own
canonical skill and seniority-level taxonomies (the `common_soft_skills` and
`common_seniority_levels` MCP resources). The agent's JSON output is validated and, on
failure, corrected through up to `max_retries` follow-up turns on the same session.
"""

import json
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
from pydantic import BaseModel, ValidationError

from ...observability import ToolObservability
from ...settings import get_skill_agent_settings
from ..mcp_server import mcp
from ..resources.common_seniority_levels import (
    COMMON_SENIORITY_LEVELS,
    normalize_seniority_level,
)
from ..resources.common_soft_skills import (
    COMMON_SOFT_SKILLS,
    normalize_soft_skill,
)

logger = get_logger(__name__)

# Flattened once at import time: {canonical_skill: [aliases]}, dropping the category
# grouping COMMON_SOFT_SKILLS uses - the agent only needs the name/alias mapping.
_CANONICAL_SKILLS = {
    canonical: aliases
    for skills in COMMON_SOFT_SKILLS.values()
    for canonical, aliases in skills.items()
}

_AGENT_DEFINITION = AgentDefinition(
    description=(
        "Extracts canonical soft skills, seniority level and years of experience "
        "from IT resumes and job postings."
    ),
    # Pinned, not the "sonnet" alias: the alias resolves to whatever Claude Code CLI build
    # picks as "latest sonnet", which can be a model id a given Portkey/Bedrock integration
    # hasn't allow-listed yet, failing every tool call with an API error instead of JSON.
    model="us.anthropic.claude-sonnet-5",
    tools=[],
    prompt=f"""\
You are a precise IT soft-skill extraction specialist.

Canonical soft-skill taxonomy (canonical name -> known aliases). Normalize whatever
spelling/phrasing you find in the document to the exact canonical name on the left; if a
real soft skill you find isn't in this list, report it under its most common industry name:
{json.dumps(_CANONICAL_SKILLS, ensure_ascii=False)}

Canonical seniority levels (canonical name -> known aliases). Infer the seniority level
implied for each skill (from years of experience, job title, or surrounding context) and
report the exact canonical name:
{json.dumps(COMMON_SENIORITY_LEVELS, ensure_ascii=False)}

Output contract:
- Respond with a single JSON array and nothing else - no prose, no markdown fences.
- Each array item is an object with keys "skill" (canonical name, string), "seniority_level"
  (canonical level, string) and "experience_years" (integer, your best estimate).
- For a job_posting document, also include "required" (boolean): true when the posting
  lists the skill as mandatory, false when it's optional/nice-to-have. Omit "required"
  entirely for a resume document.
- If the document has no soft skills, return an empty array: []
""",
)

_CORRECTION_PROMPT = (
    "Your previous response was not a valid JSON array matching the required schema "
    "({error}). Reply again with ONLY the corrected JSON array - no prose, no markdown fences."
)


class _SoftSkillItem(BaseModel):
    """One soft skill, as the agent must report it."""

    skill: str
    seniority_level: str
    experience_years: int | None = None
    required: bool | None = None


def _build_user_prompt(content: str, doc_type: str) -> str:
    return (
        f"Document type: {doc_type}\n\n"
        "Extract every soft skill from the document below and respond with a JSON "
        "array only, following the output contract from your instructions.\n\n"
        "--- DOCUMENT START ---\n"
        f"{content}\n"
        "--- DOCUMENT END ---"
    )


def _extract_json_array(raw_text: str) -> str:
    """Pulls the JSON array out of the agent's final text, tolerating stray prose/fences."""
    text = raw_text.strip()
    if "```" in text:
        text = text.split("```")[1].removeprefix("json").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON array found in the agent's response")
    return text[start : end + 1]


def _parse_skills(raw_text: str, doc_type: str) -> list[dict]:
    """Validates the agent's raw text against the skill schema and canonicalizes it."""
    items = [
        _SoftSkillItem.model_validate(item)
        for item in json.loads(_extract_json_array(raw_text))
    ]

    results = []
    for item in items:
        item.skill = normalize_soft_skill(item.skill) or item.skill
        item.seniority_level = (
            normalize_seniority_level(item.seniority_level) or item.seniority_level
        )
        item.required = bool(item.required) if doc_type == "job_posting" else None
        results.append(item.model_dump(exclude_none=True))
    return results


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


@mcp.tool()
async def extract_soft_skills(
    content: str,
    doc_type: Literal["resume", "job_posting"],
    max_retries: int = 2,
    correlation_id: str = "",
) -> list[dict]:
    """
    Extracts soft skills from resume or job-posting text, using a Claude Agent SDK
    agent grounded in the project's canonical skill/seniority taxonomy.

    Each returned item reports the skill's canonical name, seniority level and estimated
    years of experience. For a job posting, each item additionally reports whether the
    skill is required (true) or optional/nice-to-have (false); resumes omit that field.

    Args:
        content: Plain text of the resume or job posting to analyze.
        doc_type: "resume" or "job_posting".
        max_retries: Max correction attempts if the agent's JSON output fails validation.
        correlation_id: Cross-service id propagated by the coordinator so this call's
            prompt-log/transcript entries can be joined with the coordinator's own run.
            Empty when the caller doesn't provide one (e.g. manual MCP Inspector calls).
    """
    logger.info(
        "Running extract_soft_skills for doc_type=%s (max_retries=%d)",
        doc_type,
        max_retries,
    )

    options = ClaudeAgentOptions(
        env=get_agent_environment(get_agent_settings()).env,
        system_prompt=_AGENT_DEFINITION.prompt,
        model=_AGENT_DEFINITION.model,
        tools=_AGENT_DEFINITION.tools,
    )
    observability = ToolObservability(
        get_skill_agent_settings(),
        tool_name="extract_soft_skills",
        correlation_id=correlation_id,
        model=_AGENT_DEFINITION.model,
        system_prompt=_AGENT_DEFINITION.prompt,
    )

    attempts = max(max_retries, 0) + 1
    prompt = _build_user_prompt(content, doc_type)
    last_error: Exception | None = None

    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(attempts):
            observability.log_attempt_prompt(prompt=prompt, attempt=attempt + 1)
            raw_text, session_id = await _ask(client, prompt)
            observability.log_attempt_response(text=raw_text, session_id=session_id)
            try:
                result = _parse_skills(raw_text, doc_type)
                observability.log_success(result=result)
                return result
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "extract_soft_skills attempt %d/%d returned invalid output: %s",
                    attempt + 1,
                    attempts,
                    exc,
                )
                prompt = _CORRECTION_PROMPT.format(error=exc)
                observability.log_retry(attempt=attempt + 1, attempts=attempts, error=str(exc))

    observability.log_failure(error=str(last_error))
    raise RuntimeError(
        f"extract_soft_skills: agent failed to produce valid JSON after "
        f"{attempts} attempt(s): {last_error}"
    )
