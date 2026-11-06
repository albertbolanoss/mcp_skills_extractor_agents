"""MCP tool for resume/job-posting extraction: Technical Skills.

A thin `@mcp.tool()` wrapper delegating to `run_technical_skills_pipeline`, which runs
the evidence-grounded Generator-Evaluator pipeline: a single-turn Claude Agent SDK
Extractor (sonnet) grounded in the project's own canonical skill/seniority taxonomies,
followed by concurrent per-batch Claude Agent SDK Evaluator (haiku) audits and a
deterministic Python synthesis pass. See
`src/mcp_skills_extractor_agents/agents/technical_skills/` for the pipeline itself.
"""

from typing import Literal

from labs_agent_lib import get_logger

from ..mcp_server import mcp

logger = get_logger(__name__)


@mcp.tool()
async def extract_technical_skills(
    content: str,
    doc_type: Literal["resume", "job_posting"],
    max_retries: int = 2,
    correlation_id: str = "",
) -> list[dict]:
    """
    Extracts technical skills from resume or job-posting text, using an evidence-
    grounded Generator-Evaluator Claude Agent SDK pipeline.

    Each returned item reports the skill's canonical name, seniority level and
    years of experience (each `None` when not determinable with certainty), plus a
    per-field `evidences` object (`grounding_text`, `justification`,
    `evaluator_justification`, `accuracy`) auditing every one of those values against
    the source document. For a job posting, each item additionally reports whether
    the skill is required (true) or optional/nice-to-have (false), with its own
    evidence entry; resumes omit that field entirely.

    Args:
        content: Plain text of the resume or job posting to analyze.
        doc_type: "resume" or "job_posting".
        max_retries: Max self-correction attempts per agent session (the Extractor,
            and independently each Evaluator batch) if its JSON output fails validation.
        correlation_id: Cross-service id propagated by the coordinator so this call's
            prompt-log/transcript entries can be joined with the coordinator's own run.
            Empty when the caller doesn't provide one (e.g. manual MCP Inspector calls).
    """
    # Imported here, not at module level: `agents.technical_skills` (transitively, via
    # its prompt/taxonomy embedding) depends on `server.resources`, and importing any
    # submodule of `server` first fully runs `server/__init__.py`, which eagerly
    # registers every tool module in this package (see `server/mcp_server.py`). A
    # top-level import here would deadlock the first time anything imports
    # `agents.technical_skills` before `server` has finished that registration pass.
    from ...agents.technical_skills import run_technical_skills_pipeline

    logger.info(
        "Running extract_technical_skills for doc_type=%s (max_retries=%d)",
        doc_type,
        max_retries,
    )
    return await run_technical_skills_pipeline(
        content=content,
        doc_type=doc_type,
        max_retries=max_retries,
        correlation_id=correlation_id,
    )
