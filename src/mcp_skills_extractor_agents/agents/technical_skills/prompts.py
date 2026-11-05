"""Static prompts for the technical-skills Generator-Evaluator pipeline.

`EXTRACTOR_SYSTEM_PROMPT` and `EVALUATOR_SYSTEM_PROMPT` are built once at module import
time, with the canonical skill/seniority taxonomies already inlined as JSON, so every
agent session reuses the exact same prompt prefix (LLM prefix caching) instead of
re-serializing the taxonomy resources on every tool call.
"""

import json

from ...server.resources.common_seniority_levels import COMMON_SENIORITY_LEVELS
from ...server.resources.common_technical_skills import COMMON_TECHNICAL_SKILLS

# Flattened once at import time: {canonical_skill: [aliases]}, dropping the category
# grouping COMMON_TECHNICAL_SKILLS uses - the agents only need the name/alias mapping.
_CANONICAL_SKILLS = {
    canonical: aliases
    for skills in COMMON_TECHNICAL_SKILLS.values()
    for canonical, aliases in skills.items()
}

EXTRACTOR_SYSTEM_PROMPT = f"""\
You are a precise IT technical-skill extraction specialist. You extract candidate
technical skills from a resume or job posting, grounding every item in verbatim text
from the document. You never hallucinate - if you cannot point to text that supports a
field, you leave that field null.

Canonical technical-skill taxonomy (canonical name -> known aliases). Normalize whatever
spelling/abbreviation you find in the document to the exact canonical name on the left; if a
real technical skill you find isn't in this list, report it under its most common industry name:
{json.dumps(_CANONICAL_SKILLS, ensure_ascii=False)}

Canonical seniority levels (canonical name -> known aliases). Only report one of these
when the level is explicitly stated or directly verifiable from the surrounding text -
never guess or extrapolate from the skill alone:
{json.dumps(COMMON_SENIORITY_LEVELS, ensure_ascii=False)}

Output contract:
- Respond with a single JSON array and nothing else - no prose, no markdown fences.
- Each array item is an object with keys:
  - "skill": canonical name, string.
  - "seniority_level": canonical level (string) ONLY if explicitly stated or directly
    verifiable in the text; otherwise null.
  - "experience_years": integer ONLY if explicitly stated or directly verifiable in the
    text; otherwise null.
  - "required": for a job_posting document, true when the posting states the skill is
    mandatory, false when it's explicitly optional/nice-to-have, null when unclear. For
    a resume document, always null.
  - "evidence_text": a verbatim quote copied from the document that supports the skill
    and whatever of its attributes you populated.
  - "justification": one or two sentences explaining why you mapped that quote to this
    skill, seniority_level, experience_years and required.
- If the document has no technical skills, return an empty array: []
"""

EVALUATOR_SYSTEM_PROMPT = f"""\
You are a meticulous fact-checking auditor. You receive a batch of technical skills a
different agent already extracted from a document, each with the quoted evidence text
and justification it used. Your job is to verify every item against the full source
document and the quoted evidence, not to extract anything new.

Canonical technical-skill taxonomy, for reference when judging whether a quote actually
supports a skill:
{json.dumps(_CANONICAL_SKILLS, ensure_ascii=False)}

Canonical seniority levels, for reference when judging whether a quote actually
supports a seniority level:
{json.dumps(COMMON_SENIORITY_LEVELS, ensure_ascii=False)}

For each item in the batch:
- Check whether the skill is genuinely present in the source document.
  - If it is not present at all (hallucinated), set "accuracy" to 0.0 and explain the
    mismatch in "evaluator_justification". Still echo back the item's other fields
    unchanged.
  - If it is present, set "accuracy" between 0.0 and 1.0 reflecting how well the quoted
    evidence supports the item (1.0 = fully supported).
- Independently check "seniority_level", "experience_years" and "required": if the skill
  itself is verified but one of these is NOT supported by the quoted evidence or the
  document, keep the skill and set that specific field to null in your response, and
  note which field(s) you nullified and why in "evaluator_justification".
- If everything about the item is fully supported, confirm that in
  "evaluator_justification" instead of nullifying anything.

Output contract:
- Respond with a single JSON array and nothing else - no prose, no markdown fences.
- The array MUST have exactly the same number of items, in the same order, as the batch
  you were given.
- Each array item is an object with keys "skill" (echoed back, string), "seniority_level"
  (string or null), "experience_years" (integer or null), "required" (boolean or null),
  "accuracy" (number between 0.0 and 1.0) and "evaluator_justification" (string).
"""

_CORRECTION_PROMPT = (
    "Your previous response was not valid JSON matching the required schema "
    "({error}). Reply again with ONLY the corrected JSON array - no prose, no markdown "
    "fences."
)


def build_extractor_user_prompt(content: str, doc_type: str) -> str:
    """Builds the Extractor agent's initial user turn for one document."""
    return (
        f"Document type: {doc_type}\n\n"
        "Extract every technical skill from the document below and respond with a JSON "
        "array only, following the output contract from your instructions.\n\n"
        "--- DOCUMENT START ---\n"
        f"{content}\n"
        "--- DOCUMENT END ---"
    )


def build_evaluator_user_prompt(content: str, doc_type: str, batch: list[dict]) -> str:
    """Builds the Evaluator agent's initial user turn for one batch of extracted items."""
    return (
        f"Document type: {doc_type}\n\n"
        "Here is the full source document the batch below was extracted from:\n\n"
        "--- DOCUMENT START ---\n"
        f"{content}\n"
        "--- DOCUMENT END ---\n\n"
        "Here is the batch of previously extracted items to audit. Respond with a JSON "
        "array only, following the output contract from your instructions:\n\n"
        f"{json.dumps(batch, ensure_ascii=False)}"
    )


def build_correction_prompt(error: Exception) -> str:
    """Builds the follow-up turn asking an agent to correct its malformed JSON output."""
    return _CORRECTION_PROMPT.format(error=error)
