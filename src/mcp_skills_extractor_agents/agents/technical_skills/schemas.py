"""Pydantic v2 data contracts for the technical-skills Generator-Evaluator pipeline.

These are the canonical, public shapes returned by `run_technical_skills_pipeline`. The
Extractor/Evaluator agents' raw, less-strict JSON is validated against private models
local to `orchestrator.py` before being folded into these.
"""

from pydantic import BaseModel, Field


class TechnicalSkillEvidence(BaseModel):
    """Evidence and audit trail for a single extracted technical skill."""

    text: str = Field(
        description="Verbatim quote from the source document supporting the extraction."
    )
    accuracy: float = Field(
        default=-1.0,
        description=(
            "Verification score assigned by the evaluator (0.0 to 1.0), or -1.0 prior "
            "to evaluation."
        ),
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
