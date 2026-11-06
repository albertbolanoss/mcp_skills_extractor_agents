"""Pydantic v2 data contracts for the evidence-grounded technical-skills pipeline.

Every extracted field carries its own `FieldEvidence` (grounding quote, justification,
evaluator audit and accuracy score) instead of a single flat justification per item, so
the Extractor, Evaluator and deterministic Synthesizer can all reason about - and
override - one field at a time. The `model_validator(mode="before")` hooks below exist
so a slightly-under-specified agent response (a missing `justification`, an explicit
JSON `null` for `seniority_level`/`experience_years` instead of an empty evidence
object) still hydrates into a fully-populated, schema-valid model instead of failing
validation outright.
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

DEFAULT_NULL_JUSTIFICATION = "Not explicitly stated or verifiable from chronological or role context in the document."


class FieldEvidence(BaseModel):
    """Evidence and audit trail for an individual extracted field."""

    grounding_text: str = Field(
        default="",
        description=(
            "Verbatim quote from the source document supporting the field value, "
            "or empty string if the field could not be determined."
        ),
    )
    justification: str = Field(
        default=DEFAULT_NULL_JUSTIFICATION,
        description=(
            "Extractor's rationale for the extracted value, or explanation of why "
            "grounding_text is empty when the value cannot be determined."
        ),
    )
    evaluator_justification: str | None = Field(
        default=None,
        description="Evaluator's audit rationale explaining verification, correction, or nullification.",
    )
    accuracy: float = Field(
        default=-1.0,
        description="Verification score assigned by the evaluator (0.0 to 1.0), or -1.0 prior to evaluation.",
    )

    @model_validator(mode="before")
    @classmethod
    def _hydrate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            justification = data.get("justification")
            if justification is None or (
                isinstance(justification, str) and not justification.strip()
            ):
                return {**data, "justification": DEFAULT_NULL_JUSTIFICATION}
        return data


class SkillEvidences(BaseModel):
    """Per-field evidence breakdown for a single technical skill item."""

    skill: FieldEvidence
    seniority_level: FieldEvidence = Field(
        default_factory=lambda: FieldEvidence(
            grounding_text="", justification=DEFAULT_NULL_JUSTIFICATION
        )
    )
    experience_years: FieldEvidence = Field(
        default_factory=lambda: FieldEvidence(
            grounding_text="", justification=DEFAULT_NULL_JUSTIFICATION
        )
    )
    required: FieldEvidence | None = None

    @model_validator(mode="before")
    @classmethod
    def _ensure_secondary_evidences(cls, data: Any) -> Any:
        if isinstance(data, dict):
            out = dict(data)
            for key in ("seniority_level", "experience_years"):
                if out.get(key) is None:
                    out[key] = {
                        "grounding_text": "",
                        "justification": DEFAULT_NULL_JUSTIFICATION,
                    }
            return out
        return data


class TechnicalSkillItem(BaseModel):
    """Canonical representation of an extracted and evaluated technical skill."""

    skill: str
    seniority_level: str | None = None
    experience_years: int | None = None
    required: bool | None = None
    evidences: SkillEvidences
