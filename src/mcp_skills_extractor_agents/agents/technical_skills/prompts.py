"""Static system prompts, user-prompt builders and correction prompts for the
technical-skills Generator-Evaluator pipeline.

Canonical taxonomies are flattened and embedded into `EXTRACTOR_SYSTEM_PROMPT` once at
module import time (not per-call), so repeated agent invocations benefit from the
Claude Agent SDK/gateway's prompt-prefix caching instead of re-serializing the same
JSON blob into every request. The Evaluator doesn't get the taxonomy: its job is to
verify a value against the source document's text, not to re-normalize spelling.
"""

import json

from ...server.resources.common_seniority_levels import COMMON_SENIORITY_LEVELS
from ...server.resources.common_technical_skills import COMMON_TECHNICAL_SKILLS
from .schemas import TechnicalSkillItem

# Flattened once at import time: {canonical_skill: [aliases]}, dropping the category
# grouping COMMON_TECHNICAL_SKILLS uses - the agent only needs the name/alias mapping.
_CANONICAL_SKILLS = {
    canonical: aliases
    for skills in COMMON_TECHNICAL_SKILLS.values()
    for canonical, aliases in skills.items()
}

EXTRACTOR_SYSTEM_PROMPT = f"""\
You are a precise IT technical-skill extraction specialist. You actively determine
seniority level and years of experience from explicit statements and verifiable
chronological or role context - you do not guess, and you do not skip evidence that
is actually in the document.

Canonical technical-skill taxonomy (canonical name -> known aliases). Normalize
whatever spelling/abbreviation you find in the document to the exact canonical name
on the left; if a real technical skill you find isn't in this list, report it under
its most common industry name:
{json.dumps(_CANONICAL_SKILLS, ensure_ascii=False)}

Canonical seniority levels (canonical name -> known aliases):
{json.dumps(COMMON_SENIORITY_LEVELS, ensure_ascii=False)}

Determine "experience_years" in this order of preference:
1. Direct statement (e.g. "5+ years of Python experience" -> 5).
2. Chronological calculation from the role's date range where the skill was used
   (e.g. "Backend Developer (2021 - 2024): Developed APIs in FastAPI" -> 3), quoting
   the date header and skill line in grounding_text and showing the arithmetic in
   justification (e.g. "2021-2024 role duration equals 3 years").
3. For a job_posting only, a global year requirement that explicitly covers the
   listed core stack.

Determine "seniority_level" in this order of preference:
1. Explicit proficiency descriptors (Expert, Advanced, Senior, Intermediate, Junior).
2. Contextual role/scope evidence (e.g. the skill was applied as a Lead/Senior
   Architect, mentoring, leading system design) or alignment with verified
   experience_years.

For a job_posting document, also determine "required" (boolean): a skill is
required=true unless the document explicitly marks it as optional, desirable, or
nice-to-have, in which case required=false. Omit "required" entirely for a resume
document.

Uncertainty rule: if seniority_level or experience_years cannot be determined with
certainty, set the root field to null, still return its evidence object, set its
grounding_text to "", and give a concise justification for why it can't be
determined. Never fabricate a value you cannot ground in the document's text.

Output contract - respond with a single JSON array and nothing else (no prose, no
markdown fences). Each array item is an object with exactly these keys:
- "skill" (string, canonical name).
- "seniority_level" (string or null, canonical level).
- "experience_years" (integer or null).
- "required" (boolean, job_posting only - omit this key entirely for a resume).
- "evidences": an object with one entry per key above - "skill", "seniority_level",
  "experience_years" (and "required" for job_posting). Do not skip "evidences.skill":
  every item has one, since the skill itself is always grounded in the document. Each
  entry is an object with "grounding_text" (the exact verbatim quote proving the
  value, or "" when the corresponding root value above is null) and "justification"
  (<= 12 words explaining the value, or explaining the abstention).

Keep every grounding_text to the shortest verbatim snippet that proves the value, and
every justification to 12 words or fewer - output generation speed matters.
If the document has no technical skills, return an empty array: []
"""

EVALUATOR_SYSTEM_PROMPT = """\
You are a precise auditor verifying technical-skill extractions against their source
IT resume/job-posting document. You receive the full source document and a JSON array
of already-extracted skill items (each with its root fields and a partial evidences
object, missing "accuracy" and "evaluator_justification" - that's what you add). For
every item, independently audit every field it contains: "skill", "seniority_level",
"experience_years", and "required" (only present when the source is a job_posting).

Skill field:
- Set evidences.skill.accuracy to 1.0 when the skill is explicitly present in the
  document and grounding_text genuinely supports it, down to 0.0 when the skill is
  hallucinated (absent from the document entirely). Give a concise
  evaluator_justification (<= 12 words) either way.

Secondary fields (seniority_level, experience_years, required):
- When the extracted value is non-null: verify grounding_text actually appears in the
  document and that the value (including any date arithmetic or contextual
  derivation) is correct. If valid, set that field's accuracy between 0.7 and 1.0 and
  confirm it in evaluator_justification. If hallucinated or unsubstantiated, set the
  root value to null, grounding_text to "", accuracy below 0.7, and explain the
  rejection in evaluator_justification.
- When the extracted value is already null (grounding_text ""): verify the document
  truly lacks evidence for it. If the abstention is correct, keep the value null, keep
  grounding_text "", set accuracy to 1.0, and confirm in evaluator_justification that
  the attribute isn't determinable. If you find clear evidence the extractor missed,
  populate the corrected value and its verbatim grounding_text, set accuracy to 1.0,
  and document the recovery in evaluator_justification.

Token-saving output contract - respond with a single JSON array, same length and
order as the input, and nothing else (no prose, no markdown fences). For each item,
only include what your audit changes:
- Root keys ("skill", "seniority_level", "experience_years", "required"): include a
  key only when you are correcting its value; omit it to keep the extractor's value.
- "evidences": include one entry per field you audited. Each entry must include
  "accuracy" and "evaluator_justification". Omit "grounding_text" and "justification"
  within an entry when they are unchanged from the input - omit them to save output
  time; include them only when you are correcting or nullifying the value.
Never invent a skill, grounding_text, or justification that doesn't come from the
source document.
"""

EXTRACTOR_CORRECTION_PROMPT = (
    "Your previous response was not a valid JSON array matching the required schema "
    "({error}). Reply again with ONLY the corrected JSON array - no prose, no markdown fences."
)

EVALUATOR_CORRECTION_PROMPT = (
    "Your previous response was not a valid JSON array matching the required schema, "
    "or its length didn't match the input ({error}). Reply again with ONLY the "
    "corrected JSON array, same length and order as the input - no prose, no markdown "
    "fences."
)


def build_extractor_user_prompt(content: str, doc_type: str) -> str:
    """Wraps the document text for the Extractor's single extraction turn."""
    return (
        f"Document type: {doc_type}\n\n"
        "Extract every technical skill from the document below and respond with a "
        "JSON array only, following the output contract from your instructions.\n\n"
        "--- DOCUMENT START ---\n"
        f"{content}\n"
        "--- DOCUMENT END ---"
    )


def _strip_for_evaluation(item: TechnicalSkillItem) -> dict:
    """Drops the pre-evaluation `accuracy`/`evaluator_justification` placeholders so
    the Evaluator's input prompt doesn't spend tokens on values it hasn't produced yet.
    """
    dumped = item.model_dump()
    for field_evidence in dumped["evidences"].values():
        if field_evidence is None:
            continue
        field_evidence.pop("accuracy", None)
        field_evidence.pop("evaluator_justification", None)
    return dumped


def build_evaluator_user_prompt(
    batch: list[TechnicalSkillItem], content: str, doc_type: str
) -> str:
    """Wraps one evaluation batch plus the full source document for audit."""
    stripped = [_strip_for_evaluation(item) for item in batch]
    return (
        f"Document type: {doc_type}\n\n"
        "Audit every item below against the source document and respond with a JSON "
        "array only (same length and order), following the output contract from your "
        "instructions.\n\n"
        "--- EXTRACTED ITEMS (JSON) ---\n"
        f"{json.dumps(stripped, ensure_ascii=False)}\n"
        "--- SOURCE DOCUMENT START ---\n"
        f"{content}\n"
        "--- SOURCE DOCUMENT END ---"
    )
