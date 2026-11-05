"""MCP tool for resume/job-posting extraction: Languages.

A Claude Agent SDK agent extracts spoken/written human languages (with CEFR
proficiency level and native status) from free-text resume/job-posting content,
grounded in the project's own canonical language and proficiency-level taxonomies
(the `common_languages` and `common_language_proficiency_levels` MCP resources). The
agent's JSON output is validated and, on failure, corrected through up to
`max_retries` follow-up turns on the same session.
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
from ..resources.common_language_proficiency_levels import (
    COMMON_LANGUAGE_PROFICIENCY_LEVELS,
    normalize_language_proficiency,
)
from ..resources.common_languages import (
    COMMON_LANGUAGES,
    normalize_language,
)

logger = get_logger(__name__)

_AGENT_DEFINITION = AgentDefinition(
    description=(
        "Extracts canonical spoken/written languages, CEFR proficiency level and "
        "native status from IT resumes and job postings."
    ),
    # Pinned, not the "sonnet" alias: the alias resolves to whatever Claude Code CLI build
    # picks as "latest sonnet", which can be a model id a given Portkey/Bedrock integration
    # hasn't allow-listed yet, failing every tool call with an API error instead of JSON.
    model="us.anthropic.claude-sonnet-5",
    tools=[],
    prompt=f"""\
You are a precise human-language extraction specialist.

Canonical language taxonomy (canonical name -> known aliases, including non-English
spellings). Normalize whatever spelling you find in the document to the exact
canonical name on the left; if a real language you find isn't in this list, report it
under its most common English name:
{json.dumps(COMMON_LANGUAGES, ensure_ascii=False)}

Canonical CEFR proficiency levels (canonical level -> known aliases). Infer the level
implied for each language (from explicit mentions, context, or job requirements) and
report the exact canonical level. Even for a native/bilingual language, still report
your best CEFR estimate (typically "C2"):
{json.dumps(COMMON_LANGUAGE_PROFICIENCY_LEVELS, ensure_ascii=False)}

Output contract:
- Respond with a single JSON array and nothing else - no prose, no markdown fences.
- Each array item is an object with keys "language" (canonical name, string),
  "proficiency" (canonical CEFR level, string) and "is_native" (boolean: true when the
  document indicates it's the person's native/mother-tongue language, false otherwise).
- For a job_posting document, also include "required" (boolean): true when the
  posting lists the language as mandatory, false when it's optional/nice-to-have. Omit
  "required" entirely for a resume document.
- If the document mentions no languages, return an empty array: []
""",
)

_CORRECTION_PROMPT = (
    "Your previous response was not a valid JSON array matching the required schema "
    "({error}). Reply again with ONLY the corrected JSON array - no prose, no markdown fences."
)


class _LanguageItem(BaseModel):
    """One language, as the agent must report it."""

    language: str
    proficiency: str
    is_native: bool = False
    required: bool | None = None


def _build_user_prompt(content: str, doc_type: str) -> str:
    return (
        f"Document type: {doc_type}\n\n"
        "Extract every spoken/written language from the document below and respond "
        "with a JSON array only, following the output contract from your "
        "instructions.\n\n"
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


def _parse_languages(raw_text: str, doc_type: str) -> list[dict]:
    """Validates the agent's raw text against the language schema and canonicalizes it."""
    items = [
        _LanguageItem.model_validate(item)
        for item in json.loads(_extract_json_array(raw_text))
    ]

    results = []
    for item in items:
        item.language = normalize_language(item.language) or item.language
        item.proficiency = (
            normalize_language_proficiency(item.proficiency) or item.proficiency
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
async def extract_languages(
    content: str,
    doc_type: Literal["resume", "job_posting"],
    max_retries: int = 2,
    correlation_id: str = "",
) -> list[dict]:
    """
    Extracts spoken/written languages from resume or job-posting text, using a Claude
    Agent SDK agent grounded in the project's canonical language/proficiency taxonomy.

    Each returned item reports the language's canonical name, CEFR proficiency level
    and whether it's the person's native language. For a job posting, each item
    additionally reports whether the language is required (true) or optional/nice-to-
    have (false); resumes omit that field.

    Args:
        content: Plain text of the resume or job posting to analyze.
        doc_type: "resume" or "job_posting".
        max_retries: Max correction attempts if the agent's JSON output fails validation.
        correlation_id: Cross-service id propagated by the coordinator so this call's
            prompt-log/transcript entries can be joined with the coordinator's own run.
            Empty when the caller doesn't provide one (e.g. manual MCP Inspector calls).
    """
    logger.info(
        "Running extract_languages for doc_type=%s (max_retries=%d)",
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
        tool_name="extract_languages",
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
                result = _parse_languages(raw_text, doc_type)
                observability.log_success(result=result)
                return result
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "extract_languages attempt %d/%d returned invalid output: %s",
                    attempt + 1,
                    attempts,
                    exc,
                )
                prompt = _CORRECTION_PROMPT.format(error=exc)
                observability.log_retry(attempt=attempt + 1, attempts=attempts, error=str(exc))

    observability.log_failure(error=str(last_error))
    raise RuntimeError(
        f"extract_languages: agent failed to produce valid JSON after "
        f"{attempts} attempt(s): {last_error}"
    )
