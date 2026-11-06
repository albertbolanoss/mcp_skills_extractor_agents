"""MCP resources exposed by the MCP Skills Extractor Agents server."""

from .common_certifications import (
    COMMON_CERTIFICATIONS,
    common_certifications,
    get_certification_issuer,
    normalize_certification,
)
from .common_language_proficiency_levels import (
    COMMON_LANGUAGE_PROFICIENCY_LEVELS,
    common_language_proficiency_levels,
    normalize_language_proficiency,
)
from .common_languages import (
    COMMON_LANGUAGES,
    common_languages,
    normalize_language,
)
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
    "COMMON_CERTIFICATIONS",
    "COMMON_LANGUAGES",
    "COMMON_LANGUAGE_PROFICIENCY_LEVELS",
    "COMMON_SENIORITY_LEVELS",
    "COMMON_SOFT_SKILLS",
    "COMMON_TECHNICAL_SKILLS",
    "common_certifications",
    "common_language_proficiency_levels",
    "common_languages",
    "common_seniority_levels",
    "common_soft_skills",
    "common_technical_skills",
    "get_certification_issuer",
    "normalize_certification",
    "normalize_language",
    "normalize_language_proficiency",
    "normalize_seniority_level",
    "normalize_soft_skill",
    "normalize_technical_skill",
]
