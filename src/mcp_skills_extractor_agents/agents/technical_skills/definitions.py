"""Agent definitions for the technical-skills Generator-Evaluator pipeline.

Two agents, two different model tiers: a `sonnet`-class Extractor does the one-shot
evidence-grounded extraction, and a cheaper/faster `haiku`-class Evaluator audits the
extractor's output in concurrent batches. Both run with `tools=[]` - neither needs
built-in tool access, just a single structured-JSON turn.
"""

from claude_agent_sdk import AgentDefinition

from .prompts import EVALUATOR_SYSTEM_PROMPT, EXTRACTOR_SYSTEM_PROMPT

EXTRACTOR_AGENT_DEFINITION = AgentDefinition(
    description=(
        "Extracts canonical technical skills, seniority level and years of "
        "experience, each with grounding evidence, from IT resumes and job postings."
    ),
    # Pinned, not the "sonnet" alias: the alias resolves to whatever Claude Code CLI
    # build picks as "latest sonnet", which can be a model id a given Portkey/Bedrock
    # integration hasn't allow-listed yet, failing every call with an API error
    # instead of JSON.
    model="us.anthropic.claude-sonnet-5",
    tools=[],
    prompt=EXTRACTOR_SYSTEM_PROMPT,
)

EVALUATOR_AGENT_DEFINITION = AgentDefinition(
    description=(
        "Audits extracted technical-skill items against their source document, "
        "scoring per-field accuracy and correcting or nullifying unsubstantiated "
        "values."
    ),
    # Pinned for the same reason as EXTRACTOR_AGENT_DEFINITION above - avoids the
    # "haiku" alias resolving to a model id the gateway hasn't allow-listed yet.
    # claude-haiku-4-5 is the newest Haiku-tier id this project's Bedrock/Portkey
    # virtual key actually allow-lists (verified against the gateway's own model
    # list - there is no bare "claude-haiku-5" id there yet, unlike claude-sonnet-5).
    model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    tools=[],
    prompt=EVALUATOR_SYSTEM_PROMPT,
)
