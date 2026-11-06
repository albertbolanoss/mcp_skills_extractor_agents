"""MCP resource: canonical CEFR language-proficiency taxonomy.

A single, shared vocabulary of language-proficiency levels, based on the CEFR scale
(A1-C2) — each mapped to the alternate phrasings it's commonly found under in a
resume or job posting (e.g. "Fluent", "Upper Intermediate", "Native"). Extraction
agents use it to normalize whatever raw text they find to one canonical CEFR level,
so every agent in the pipeline reports proficiency in the same unified scale instead
of each one inventing its own label.
"""

from ..mcp_server import mcp

COMMON_LANGUAGE_PROFICIENCY_LEVELS: dict[str, list[str]] = {
    "A1": ["Beginner", "Basic"],
    "A2": ["Elementary", "Pre-Intermediate"],
    "B1": ["Intermediate", "Threshold"],
    "B2": ["Upper Intermediate", "Upper-Intermediate", "B2 - Upper Intermediate"],
    "C1": ["Advanced", "Effective Proficiency"],
    "C2": [
        "Proficient",
        "Mastery",
        "Fluent",
        "Native",
        "Native Speaker",
        "Mother Tongue",
        "Bilingual",
        "Full Professional Proficiency",
    ],
}

# lowered canonical name/alias -> canonical name, built once at import time so
# tools/agents can normalize a raw extracted string in O(1).
_ALIAS_INDEX: dict[str, str] = {
    variant.lower(): canonical
    for canonical, aliases in COMMON_LANGUAGE_PROFICIENCY_LEVELS.items()
    for variant in (canonical, *aliases)
}


def normalize_language_proficiency(raw: str) -> str | None:
    """Maps a raw proficiency string found in a resume/job posting to its canonical
    CEFR level.

    Lookup is case-insensitive against both canonical levels and their known aliases.
    Returns None if `raw` isn't present in `COMMON_LANGUAGE_PROFICIENCY_LEVELS`,
    leaving the caller free to keep the raw value or discard it.
    """
    return _ALIAS_INDEX.get(raw.strip().lower())


@mcp.resource(
    "resource://common-language-proficiency-levels",
    name="common_language_proficiency_levels",
    title="Common Language Proficiency Levels (CEFR)",
    description=(
        "Canonical CEFR language-proficiency scale (A1-C2) with its common aliases "
        "(e.g. 'Fluent', 'Upper Intermediate', 'Native'). Agents extracting language "
        "proficiency from a resume or job posting use it to normalize what they find "
        "to one shared, unified scale."
    ),
    mime_type="application/json",
)
def common_language_proficiency_levels() -> dict[str, list[str]]:
    """Returns the canonical CEFR language-proficiency taxonomy."""
    return COMMON_LANGUAGE_PROFICIENCY_LEVELS
