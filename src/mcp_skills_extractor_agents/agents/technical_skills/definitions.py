"""Claude Agent SDK agent definitions for the technical-skills pipeline.

Each `AgentDefinition` only needs its `.prompt` and `.model` consumed by the
orchestrator - `tools=[]` keeps both agents text-in/text-out, with no filesystem/bash
access, since they only ever reason over the document text they're given.
"""

from claude_agent_sdk import AgentDefinition

from .prompts import EVALUATOR_SYSTEM_PROMPT, EXTRACTOR_SYSTEM_PROMPT

EXTRACTOR_AGENT_DEFINITION = AgentDefinition(
    description=(
        "Extracts canonical technical skills, with verbatim evidence, from IT resumes "
        "and job postings."
    ),
    model="sonnet",
    tools=[],
    prompt=EXTRACTOR_SYSTEM_PROMPT,
)

EVALUATOR_AGENT_DEFINITION = AgentDefinition(
    description=(
        "Audits a batch of previously extracted technical skills against their source "
        "document and quoted evidence."
    ),
    model="haiku",
    tools=[],
    prompt=EVALUATOR_SYSTEM_PROMPT,
)
