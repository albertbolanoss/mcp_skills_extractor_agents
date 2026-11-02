"""MCP resource: canonical IT seniority-level taxonomy.

A single, shared vocabulary of seniority levels — each mapped to the alternate
titles/abbreviations it's commonly found under in a resume or job posting.
Extraction agents use it to normalize whatever raw text they find (e.g. "Sr",
"Tech Lead", "Entry-Level") to one canonical level (e.g. "Senior", "Lead",
"Junior"), so every agent in the pipeline reports seniority in the same
unified language instead of each one inventing its own label.
"""

from ..mcp_server import mcp

COMMON_SENIORITY_LEVELS: dict[str, list[str]] = {
    "Intern": ["Trainee", "Internship", "Student"],
    "Junior": ["Jr", "Jr.", "Entry-Level", "Entry Level", "Associate"],
    "Mid-Level": ["Middle", "Mid", "Intermediate"],
    "Senior": ["Sr", "Sr.", "Senior-Level"],
    "Staff": ["Staff Engineer"],
    "Lead": ["Team Lead", "Tech Lead", "Technical Lead", "Lead Engineer"],
    "Principal": ["Principal Engineer"],
    "Architect": ["Solution Architect", "Software Architect", "Technical Architect"],
    "Manager": ["Engineering Manager", "People Manager", "Development Manager"],
    "Director": ["Engineering Director", "Director of Engineering"],
    "VP": ["Vice President", "VP of Engineering", "Vice President of Engineering"],
}

# lowered canonical name/alias -> canonical name, built once at import time so
# tools/agents can normalize a raw extracted string in O(1).
_ALIAS_INDEX: dict[str, str] = {
    variant.lower(): canonical
    for canonical, aliases in COMMON_SENIORITY_LEVELS.items()
    for variant in (canonical, *aliases)
}


def normalize_seniority_level(raw: str) -> str | None:
    """Maps a raw seniority string found in a resume/job posting to its canonical name.

    Lookup is case-insensitive against both canonical names and their known aliases.
    Returns None if `raw` isn't present in `COMMON_SENIORITY_LEVELS`, leaving the
    caller free to keep the raw value or discard it.
    """
    return _ALIAS_INDEX.get(raw.strip().lower())


@mcp.resource(
    "resource://common-seniority-levels",
    name="common_seniority_levels",
    title="Common IT Seniority Levels",
    description=(
        "Canonical taxonomy of IT seniority levels (Intern, Junior, Mid-Level, Senior, "
        "Staff, Lead, Principal, Architect, Manager, Director, VP) with their common "
        "aliases. Agents extracting seniority from a resume or job posting use it to "
        "normalize what they find to one shared, unified vocabulary."
    ),
    mime_type="application/json",
)
def common_seniority_levels() -> dict[str, list[str]]:
    """Returns the canonical IT seniority-level taxonomy."""
    return COMMON_SENIORITY_LEVELS
