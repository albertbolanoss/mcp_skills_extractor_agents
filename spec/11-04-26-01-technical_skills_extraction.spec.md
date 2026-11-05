# SPEC: Evidence-Grounded Technical Skills Extraction & Evaluation

## 1. Business Goals
Extract canonical technical skills from plain-text IT resumes (`resume`) and job descriptions (`job_posting`) with zero hallucinations. Every extracted skill and attribute must be backed by verbatim textual evidence from the source document and verified by an evaluator agent before returning the final payload, maintaining low latency and optimal token consumption.

## 2. Architecture Overview (Hybrid Generator-Evaluator Pattern)
To prevent token explosion and excessive sequential LLM hops, the pipeline replaces a 4-LLM-layer architecture with a **2-LLM-stage Hybrid Generator-Evaluator pipeline**:
1. **Generator (Extractor Agent - `sonnet`)**: Extracts candidate technical skills in a single turn, grounding them against canonical taxonomies and capturing verbatim evidence (`text`) and an extraction `justification`. Unverified attributes (`seniority_level`, `experience_years`, `required`) must default to `null`.
2. **Deterministic Coordinator (Python `asyncio`)**: Splits extracted candidate skills into batches (`EVAL_BATCH_SIZE = 10`) and dispatches concurrent evaluation tasks via `asyncio.gather`.
3. **Batch Evaluator (Evaluator Agent - `haiku` or `sonnet`)**: Audits each batch against the source document, assigns an `accuracy` score (`0.0` to `1.0`), nullifies any unsubstantiated secondary attributes (`seniority_level`, `experience_years`, `required`), and writes an `evaluator_justification`.
4. **Deterministic Synthesizer (Pure Python)**: Filters out items with `accuracy < 0.7`, applies canonical normalization functions (`normalize_technical_skill`, `normalize_seniority_level`), enforces document-type field rules, and returns the clean list of dictionaries.

## 3. Functional Requirements
### 3.1 Modular Separation of Concerns
- Decouple the agent definitions, prompts, Pydantic schemas, and orchestration pipeline from the MCP tool definition file.
- Relocate all agent-specific logic into `src/agents/technical_skills/`.
- Keep the MCP tool module strictly as a thin entrypoint that delegates execution to the orchestrator.

### 3.2 Strict Evidence-Based Extraction (Generator)
- Normalize extracted skills against `COMMON_TECHNICAL_SKILLS` and seniority levels against `COMMON_SENIORITY_LEVELS`.
- Populate `seniority_level` and `experience_years` **only** if explicitly stated or directly verifiable in the text; otherwise set to `null`. Do not guess or extrapolate.
- Populate `required` (`true` for mandatory, `false` for optional/nice-to-have) **only** when `doc_type == "job_posting"` and the requirement status is clear in the text; set to `null` for `resume` documents.
- Populate `evidences.technical_skills` for every extracted item with:
  - `text`: Verbatim quote from the source document where the skill and its attributes were found.
  - `accuracy`: Initialized to `-1.0` by the extractor.
  - `justification`: Brief explanation of why the extractor mapped the text to the skill, seniority, years, and required flag.
  - `evaluator_justification`: Initialized to `null`.

### 3.3 Parallel Batch Evaluation (Coordinator & Evaluator)
- Short-circuit immediately and return `[]` if the Extractor Agent returns an empty list (do not invoke the Evaluator).
- Partition extracted items into batches of up to 10 items (`EVAL_BATCH_SIZE = 10`) and evaluate batches concurrently using `asyncio.gather`.
- For each item in a batch, the Evaluator Agent must verify the extracted fields against the full source document and the quoted `evidences.technical_skills.text`:
  - Set `accuracy` between `0.0` and `1.0` (`1.0` = completely verified by text, `0.0` = hallucinated skill not present in the document).
  - If the skill exists in the document (`accuracy >= 0.7`) but `seniority_level`, `experience_years`, or `required` is unsupported by the text, keep the skill, overwrite the unsupported field(s) to `null`, and document the modification in `evaluator_justification`.
  - If the skill is completely accurate, confirm it in `evaluator_justification`.

### 3.4 Deterministic Synthesis (Synthesizer)
- Retain only items where `evidences.technical_skills.accuracy >= 0.7` (`ACCURACY_THRESHOLD`).
- Apply `normalize_technical_skill` to `item.skill` and `normalize_seniority_level` to `item.seniority_level` (when not `None`).
- Force `item.required = None` when `doc_type == "resume"`.
- Serialize each validated item via `model_dump(exclude_none=True)`, preserving the `evidences` object structure.

## 4. Data Contracts & Pydantic v2 Schemas
File: `src/agents/technical_skills/schemas.py`

```python
from pydantic import BaseModel, Field


class TechnicalSkillEvidence(BaseModel):
    """Evidence and audit trail for a single extracted technical skill."""

    text: str = Field(
        description="Verbatim quote from the source document supporting the extraction."
    )
    accuracy: float = Field(
        default=-1.0,
        description="Verification score assigned by the evaluator (0.0 to 1.0), or -1.0 prior to evaluation.",
    )
    justification: str = Field(
        description="Extractor's rationale for skill, seniority_level, experience_years, and required."
    )
    evaluator_justification: str | None = Field(
        default=None,
        description="Evaluator's audit rationale explaining verification or field nullification.",
    )


class EvidenceContainer(BaseModel):
    """Wrapper container for domain-specific evidence payloads."""

    technical_skills: TechnicalSkillEvidence


class TechnicalSkillItem(BaseModel):
    """Canonical representation of an extracted and evaluated technical skill."""

    skill: str
    seniority_level: str | None = None
    experience_years: int | None = None
    required: bool | None = None
    evidences: EvidenceContainer
```

## 5. Technical Rules & Constraints
- **Target Directory Structure**:
  - `src/tools/extract_technical_skills.py`: Contains `@mcp.tool() async def extract_technical_skills(...)` and delegates to `run_technical_skills_pipeline`.
  - `src/agents/technical_skills/__init__.py`: Exports `run_technical_skills_pipeline`.
  - `src/agents/technical_skills/schemas.py`: Contains Pydantic v2 data models.
  - `src/agents/technical_skills/prompts.py`: Contains static system prompts, user prompt builders, and JSON correction prompts for both Extractor and Evaluator.
  - `src/agents/technical_skills/definitions.py`: Contains `EXTRACTOR_AGENT_DEFINITION` and `EVALUATOR_AGENT_DEFINITION` (`claude_agent_sdk.AgentDefinition`).
  - `src/agents/technical_skills/orchestrator.py`: Contains `ClaudeSDKClient` query helpers, retry loops, batching coordinator, and deterministic synthesizer.
- **Taxonomy Grounding & Prompt Caching**:
  - Inject flattened `_CANONICAL_SKILLS` and `COMMON_SENIORITY_LEVELS` directly into the static `system_prompt` in `prompts.py` at module import time to leverage LLM prefix caching and avoid runtime MCP resource serialization overhead.
- **Self-Correction Retry Loop**:
  - Maintain the multi-turn session retry mechanism (`max_retries: int = 2`) on the active `ClaudeSDKClient` instance whenever `json.loads`, `_extract_json_array`, or Pydantic `model_validate` raises `(json.JSONDecodeError, ValidationError, ValueError)`.
- **Concurrency & Latency Guardrails**:
  - Never spawn one LLM session per individual skill. Always batch up to `EVAL_BATCH_SIZE = 10` skills per evaluator request.

## 6. Edge Cases
1. **Empty or Non-Technical Document**: Extractor returns `[]`; orchestrator skips Evaluator execution and returns `[]` immediately.
2. **Valid Skill with Hallucinated Seniority or Experience Years**: Extractor outputs `"skill": "Python", "seniority_level": "Senior", "experience_years": 5` from a line that only says `"Experience with Python"`. Evaluator sets `accuracy = 1.0`, resets `seniority_level = null` and `experience_years = null`, and records `"Skill verified, but seniority and years were not stated in the source text"` in `evaluator_justification`.
3. **Completely Hallucinated Skill**: Extractor outputs `"Kubernetes"` when the text only mentions `"Docker"`. Evaluator sets `accuracy = 0.0` and documents the mismatch; Synthesizer removes `"Kubernetes"` from the final output.
4. **Markdown Fences or Prose Around JSON**: `_extract_json_array` strips markdown code blocks and slices from the first `[` to the last `]` before validation.
5. **Resume with `required` Field Populated**: Even if an agent mistakenly sets `required = true` on a `resume`, the deterministic synthesizer overrides `item.required = None` before calling `model_dump(exclude_none=True)`.

## 7. Exclusions (Out of Scope)
- Do not extract soft skills, spoken languages, or certifications in this module.
- Do not implement the Coordinator or Synthesizer as LLM agents; both must remain deterministic Python functions.
- Do not introduce external database persistence or state stores inside this tool execution flow.

## 8. Acceptance Criteria & Test Mapping
Each automated test in `tests/agents/technical_skills/test_technical_skills_pipeline.py` must map 1:1 to these verification criteria:
- `test_module_separation`: Confirms `src/tools/extract_technical_skills.py` contains only the `@mcp.tool()` wrapper and imports `run_technical_skills_pipeline` from `src/agents/technical_skills/orchestrator.py`.
- `test_partial_attributes_allowed`: Validates that `TechnicalSkillItem` accepts `None` for `seniority_level`, `experience_years`, and `required`, while requiring `skill` and `evidences.technical_skills`.
- `test_empty_extraction_short_circuits_evaluator`: Mocks Extractor returning `[]` and asserts the Evaluator client is called `0` times.
- `test_batch_evaluation_concurrency`: Feeds 25 extracted skills into the coordinator with `EVAL_BATCH_SIZE = 10` and asserts exactly 3 parallel evaluator batch calls are executed via `asyncio.gather`.
- `test_evaluator_nullifies_unsupported_metadata`: Simulates an evaluator batch response where `seniority_level` is set to `None` with `accuracy = 0.9` and verifies the final output retains the skill without `seniority_level` and includes `evaluator_justification`.
- `test_synthesizer_filters_low_accuracy_skills`: Feeds evaluated items with `accuracy = 0.85` and `accuracy = 0.4` into the synthesizer and asserts only the `>= 0.7` item is returned.
- `test_retry_loop_recovers_from_malformed_json`: Simulates a malformed JSON string on attempt 1 followed by a valid JSON array on attempt 2, verifying `_CORRECTION_PROMPT` is sent on the same `ClaudeSDKClient` session.
