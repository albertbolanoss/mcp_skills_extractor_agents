"""MCP tool for resume/job-posting extraction: Certifications.

A Claude Agent SDK agent extracts professional certifications (with issuer and active
status) from free-text resume/job-posting content, grounded in the project's own
canonical certification taxonomy (the `common_certifications` MCP resource). The
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
from ..resources.common_certifications import (
    COMMON_CERTIFICATIONS,
    get_certification_issuer,
    normalize_certification,
)

logger = get_logger(__name__)

# Flattened once at import time: {canonical_title: {"issuer": ..., "aliases": [...]}},
# dropping the category grouping COMMON_CERTIFICATIONS uses - the agent only needs the
# title/issuer/alias mapping.
_CANONICAL_CERTIFICATIONS = {
    canonical: info
    for certs in COMMON_CERTIFICATIONS.values()
    for canonical, info in certs.items()
}

_AGENT_DEFINITION = AgentDefinition(
    description=(
        "Extracts canonical professional certifications, their issuer and active "
        "status from IT resumes and job postings."
    ),
    # Pinned, not the "sonnet" alias: the alias resolves to whatever Claude Code CLI build
    # picks as "latest sonnet", which can be a model id a given Portkey/Bedrock integration
    # hasn't allow-listed yet, failing every tool call with an API error instead of JSON.
    model="us.anthropic.claude-sonnet-5",
    tools=[],
    prompt=f"""\
You are a precise IT certification extraction specialist.

Canonical certification taxonomy (canonical title -> issuer and known aliases).
Normalize whatever spelling/abbreviation you find in the document to the exact
canonical title and issuer on the left; if a real certification you find isn't in this
list, report it under its most common industry title and its actual issuer:
{json.dumps(_CANONICAL_CERTIFICATIONS, ensure_ascii=False)}

Output contract:
- Respond with a single JSON array and nothing else - no prose, no markdown fences.
- Each array item is an object with keys "title" (canonical title, string), "issuer"
  (issuing organization, string) and "is_active" (boolean: true unless the document
  says the certification expired, was revoked, or is no longer valid).
- For a job_posting document, also include "required" (boolean): true when the posting
  lists the certification as mandatory, false when it's optional/nice-to-have. Omit
  "required" entirely for a resume document.
- If the document has no certifications, return an empty array: []
""",
)

_CORRECTION_PROMPT = (
    "Your previous response was not a valid JSON array matching the required schema "
    "({error}). Reply again with ONLY the corrected JSON array - no prose, no markdown fences."
)


class _CertificationItem(BaseModel):
    """One certification, as the agent must report it."""

    title: str
    issuer: str
    is_active: bool = True
    required: bool | None = None


def _build_user_prompt(content: str, doc_type: str) -> str:
    return (
        f"Document type: {doc_type}\n\n"
        "Extract every professional certification from the document below and respond "
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


def _parse_certifications(raw_text: str, doc_type: str) -> list[dict]:
    """Validates the agent's raw text against the certification schema and canonicalizes it."""
    items = [
        _CertificationItem.model_validate(item)
        for item in json.loads(_extract_json_array(raw_text))
    ]

    results = []
    for item in items:
        canonical = normalize_certification(item.title)
        if canonical:
            item.title = canonical
            item.issuer = get_certification_issuer(canonical) or item.issuer
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
async def extract_certifications(
    content: str,
    doc_type: Literal["resume", "job_posting"],
    max_retries: int = 2,
    correlation_id: str = "",
) -> list[dict]:
    """
    Extracts professional certifications from resume or job-posting text, using a
    Claude Agent SDK agent grounded in the project's canonical certification
    taxonomy.

    Each returned item reports the certification's canonical title, issuer and
    whether it's currently active. For a job posting, each item additionally reports
    whether the certification is required (true) or optional/nice-to-have (false);
    resumes omit that field.

    Args:
        content: Plain text of the resume or job posting to analyze.
        doc_type: "resume" or "job_posting".
        max_retries: Max correction attempts if the agent's JSON output fails validation.
        correlation_id: Cross-service id propagated by the coordinator so this call's
            prompt-log/transcript entries can be joined with the coordinator's own run.
            Empty when the caller doesn't provide one (e.g. manual MCP Inspector calls).
    """
    logger.info(
        "Running extract_certifications for doc_type=%s (max_retries=%d)",
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
        tool_name="extract_certifications",
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
                result = _parse_certifications(raw_text, doc_type)
                observability.log_success(result=result)
                return result
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "extract_certifications attempt %d/%d returned invalid output: %s",
                    attempt + 1,
                    attempts,
                    exc,
                )
                prompt = _CORRECTION_PROMPT.format(error=exc)
                observability.log_retry(attempt=attempt + 1, attempts=attempts, error=str(exc))

    observability.log_failure(error=str(last_error))
    raise RuntimeError(
        f"extract_certifications: agent failed to produce valid JSON after "
        f"{attempts} attempt(s): {last_error}"
    )
