"""MCP tool for resume/job-posting extraction: Technical Skills.

Thin entrypoint only - all agent definitions, prompts, Pydantic schemas and the
Generator-Evaluator orchestration pipeline live under
`mcp_skills_extractor_agents.agents.technical_skills`.
"""

from typing import Literal

from ..mcp_server import mcp


@mcp.tool()
async def extract_technical_skills(
    content: str,
    doc_type: Literal["resume", "job_posting"],
    max_retries: int = 2,
) -> list[dict]:
    """
    Extracts evidence-grounded technical skills from resume or job-posting text.

    Runs a Generator-Evaluator pipeline: a Claude Agent SDK agent extracts candidate
    skills with verbatim supporting evidence, then a second agent audits each one
    against the source document before low-accuracy items are filtered out.

    Each returned item reports the skill's canonical name, seniority level, estimated
    years of experience (each only when explicitly supported by the text) and the
    evidence used to verify it. For a job posting, each item additionally reports
    whether the skill is required (true) or optional/nice-to-have (false); resumes
    omit that field.

    Args:
        content: Plain text of the resume or job posting to analyze.
        doc_type: "resume" or "job_posting".
        max_retries: Max self-correction attempts per agent session if its JSON
            output fails validation.
    """
    # Imported lazily: agents.technical_skills pulls in server.resources at module
    # import time (for prompt-caching), which would otherwise re-enter this module
    # through server.tools before it finished loading if imported eagerly here.
    from ...agents.technical_skills import run_technical_skills_pipeline

    return await run_technical_skills_pipeline(content, doc_type, max_retries)
