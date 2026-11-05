"""Pydantic v2 data contracts for the technical-skills Generator-Evaluator pipeline.

These are the canonical, public shapes returned by `run_technical_skills_pipeline`, and
are also the shapes the Extractor/Evaluator agents' raw JSON is validated against
directly - see `orchestrator.py`.
"""

from pydantic import BaseModel, Field


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


class SkillEvidences(BaseModel):
    """Per-field evidence breakdown for a single technical skill item."""

    skill: FieldEvidence
    seniority_level: FieldEvidence
    experience_years: FieldEvidence
    required: FieldEvidence | None = None


class TechnicalSkillItem(BaseModel):
    """Canonical representation of an extracted and evaluated technical skill."""

    skill: str
    seniority_level: str | None = None
    experience_years: int | None = None
    required: bool | None = None
    evidences: SkillEvidences
