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
technical skills, and actively attempt to determine each skill's seniority_level,
experience_years and (for job postings) required flag, grounding every field in
verbatim text from the document. You never hallucinate - if you cannot point to text
that supports a field, you leave that field null and explain why in its justification.

Canonical technical-skill taxonomy (canonical name -> known aliases). Normalize whatever
spelling/abbreviation you find in the document to the exact canonical name on the left; if a
real technical skill you find isn't in this list, report it under its most common industry name:
{json.dumps(_CANONICAL_SKILLS, ensure_ascii=False)}

Canonical seniority levels (canonical name -> known aliases). Only report one of these
when the level is explicitly stated or directly verifiable from the surrounding text -
never guess or extrapolate from the skill alone:
{json.dumps(COMMON_SENIORITY_LEVELS, ensure_ascii=False)}

How to determine "experience_years" (try each in order, use the first that applies):
1. Direct statement - e.g. "5+ years of Python experience" -> 5.
2. Chronological calculation from an explicit role date range where the skill was used -
   e.g. "Backend Developer (2021 - 2024): Developed APIs in FastAPI" -> 3. Quote the date
   header and the skill line in grounding_text, and show the calculation in
   justification.
3. For job postings only: role/posting requirement propagation - a global year
   requirement that explicitly covers the listed core stack.
If none of these apply, leave it null.

How to determine "seniority_level" (try each in order, use the first that applies):
1. Explicit proficiency descriptors - e.g. "Expert", "Advanced", "Senior",
   "Intermediate", "Junior".
2. Contextual role/scope evidence - e.g. applying the skill as a "Lead/Senior
   Architect", mentoring teams, leading system design, or clearly aligning with a
   verified experience_years in context.
If neither applies, leave it null.

Output contract:
- Respond with a single JSON array and nothing else - no prose, no markdown fences.
- Each array item is an object with keys:
  - "skill": canonical name, string.
  - "seniority_level": canonical level (string) or null.
  - "experience_years": integer or null.
  - "required": ONLY when document type is "job_posting" (omit this key entirely for
    "resume"). true when the posting states the skill is mandatory/core, false when
    it's explicitly optional/preferred/nice-to-have. If the posting doesn't say either
    way, default to true and say so in its justification - a skill is only optional
    when the text explicitly marks it as such.
  - "evidences": an object with a per-field evidence object for "skill",
    "seniority_level", "experience_years", and (job_posting only, matching the
    "required" key above) "required". Each evidence object has:
    - "grounding_text": verbatim quote from the document supporting that field's
      value, or "" if the field is null.
    - "justification": one or two sentences explaining how the quote supports the
      value (e.g. showing the date-range math), or why the field could not be
      determined when grounding_text is "".
- If the document has no technical skills, return an empty array: []
"""

EVALUATOR_SYSTEM_PROMPT = f"""\
You are a meticulous fact-checking auditor. You receive a batch of technical skills a
different agent already extracted from a document, each with per-field grounding_text
and justification. Your job is to verify every field of every item against the full
source document, not to extract anything new.

Canonical technical-skill taxonomy, for reference when judging whether a quote actually
supports a skill:
{json.dumps(_CANONICAL_SKILLS, ensure_ascii=False)}

Canonical seniority levels, for reference when judging whether a quote actually
supports a seniority level:
{json.dumps(COMMON_SENIORITY_LEVELS, ensure_ascii=False)}

For each item in the batch, audit every field independently:

- "evidences.skill": Set "accuracy" between 0.0 and 1.0 reflecting how well the
  document supports the skill being genuinely present (1.0 = explicitly present and
  supported by grounding_text, 0.0 = hallucinated, not in the document at all).
  Explain your verdict in "evaluator_justification".

- "seniority_level", "experience_years" and (job_posting only) "required": each has a
  root value and a matching "evidences.<field>" object.
  - When the extracted value is non-null: verify that grounding_text genuinely appears
    in the source document and that the value (including any date math or contextual
    derivation) is accurate.
    - If valid: keep the root value, grounding_text and justification; set that field's
      "accuracy" between 0.7 and 1.0; confirm the verification in
      "evaluator_justification".
    - If hallucinated or unsubstantiated: set the root field value to null, set
      "grounding_text" to "", set "accuracy" below 0.7 (0.0 to <0.7), and explain the
      rejection in "evaluator_justification".
  - When the extracted value is null (grounding_text == ""): verify whether the
    document genuinely lacks sufficient evidence.
    - If the abstention is correct: keep the field null, keep "grounding_text" as "",
      set "accuracy" to 1.0, and confirm in "evaluator_justification" that the
      attribute is indeed not determinable from the text.
    - If you find clear evidence the extractor missed: populate the root field value
      and a verbatim "grounding_text" quote, set "accuracy" to 1.0, update
      "justification" to explain the recovered value, and document the recovery in
      "evaluator_justification".

Output contract:
- Respond with a single JSON array and nothing else - no prose, no markdown fences.
- The array MUST have exactly the same number of items, in the same order, as the batch
  you were given, with exactly the same keys each item was given (including "required"
  and "evidences.required" only when present in the input item).
- Every evidence object in your response must include all four keys: "grounding_text",
  "justification", "evaluator_justification", and "accuracy".
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
