"""MCP resources exposed by the Candidate Skill Agent server."""

from .common_seniority_levels import (
    COMMON_SENIORITY_LEVELS,
    common_seniority_levels,
    normalize_seniority_level,
)
from .common_soft_skills import (
    COMMON_SOFT_SKILLS,
    common_soft_skills,
    normalize_soft_skill,
)
from .common_technical_skills import (
    COMMON_TECHNICAL_SKILLS,
    common_technical_skills,
    normalize_technical_skill,
)

__all__ = [
    "COMMON_SENIORITY_LEVELS",
    "COMMON_SOFT_SKILLS",
    "COMMON_TECHNICAL_SKILLS",
    "common_seniority_levels",
    "common_soft_skills",
    "common_technical_skills",
    "normalize_seniority_level",
    "normalize_soft_skill",
    "normalize_technical_skill",
]
