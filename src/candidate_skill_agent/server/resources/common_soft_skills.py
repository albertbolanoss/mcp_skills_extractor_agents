"""MCP resource: canonical IT soft-skill taxonomy.

A single, shared vocabulary of soft skills — grouped by category, each mapped to the
alternate spellings/phrasings it's commonly found under in a resume or job posting.
Extraction tools/agents use it to normalize whatever raw text they find (e.g. "Team
Player", "People Management") to one canonical name (e.g. "Teamwork", "People
Management"), so every agent in the pipeline stores and reports skills in the same
unified language instead of each one inventing its own spelling.
"""

from ..mcp_server import mcp

COMMON_SOFT_SKILLS: dict[str, dict[str, list[str]]] = {
    "leadership": {
        "Leadership": ["Team Leadership", "Leading Teams"],
        "People Management": ["Managing People", "Staff Management"],
        "Mentoring": ["Coaching", "Mentorship"],
        "Technical Leadership": ["Tech Leadership"],
        "Delegation": [],
        "Strategic Thinking": ["Strategic Planning"],
    },
    "communication": {
        "Communication": ["Verbal Communication", "Written Communication"],
        "Public Speaking": ["Presentation Skills", "Presenting"],
        "Active Listening": [],
        "Storytelling": [],
        "Technical Writing": [],
    },
    "collaboration_teamwork": {
        "Teamwork": ["Team Player", "Team Collaboration"],
        "Cross-functional Collaboration": ["Cross-team Collaboration"],
        "Relationship Building": ["Rapport Building"],
        "Stakeholder Management": [],
    },
    "problem_solving": {
        "Problem Solving": ["Problem-Solving"],
        "Critical Thinking": [],
        "Analytical Thinking": ["Analytical Skills"],
        "Troubleshooting": [],
        "Decision Making": ["Decision-Making"],
    },
    "adaptability_resilience": {
        "Adaptability": ["Flexibility"],
        "Resilience": ["Stress Management"],
        "Growth Mindset": ["Continuous Learning"],
    },
    "work_ethic_professionalism": {
        "Work Ethic": ["Strong Work Ethic"],
        "Reliability": ["Dependability"],
        "Accountability": ["Ownership"],
        "Attention to Detail": ["Detail-Oriented"],
        "Time Management": ["Prioritization", "Multitasking"],
        "Organization": ["Organizational Skills"],
    },
    "creativity_innovation": {
        "Creativity": [],
        "Innovation": [],
        "Design Thinking": [],
    },
    "emotional_intelligence": {
        "Emotional Intelligence": ["EQ"],
        "Empathy": [],
        "Self-Awareness": [],
        "Conflict Resolution": [],
    },
    "interpersonal": {
        "Interpersonal Skills": [],
        "Negotiation": [],
        "Persuasion": [],
        "Networking": [],
    },
    "customer_orientation": {
        "Customer Service": ["Client Management", "Customer Focus"],
        "Customer Orientation": [],
    },
}

# category -> {canonical_name, lowered, for a canonical name or alias}, built once at import
# time so tools/agents can normalize a raw extracted string in O(1) without re-scanning
# COMMON_SOFT_SKILLS on every lookup.
_ALIAS_INDEX: dict[str, tuple[str, str]] = {
    variant.lower(): (category, canonical)
    for category, skills in COMMON_SOFT_SKILLS.items()
    for canonical, aliases in skills.items()
    for variant in (canonical, *aliases)
}


def normalize_soft_skill(raw: str) -> str | None:
    """Maps a raw skill string found in a resume/job posting to its canonical name.

    Lookup is case-insensitive against both canonical names and their known aliases.
    Returns None if `raw` isn't present in `COMMON_SOFT_SKILLS`, leaving the caller
    free to keep the raw value or discard it.
    """
    match = _ALIAS_INDEX.get(raw.strip().lower())
    return match[1] if match else None


@mcp.resource(
    "resource://common-soft-skills",
    name="common_soft_skills",
    title="Common IT Soft Skills",
    description=(
        "Canonical taxonomy of soft skills (leadership, communication, collaboration, "
        "problem solving, adaptability, work ethic, creativity, emotional intelligence, "
        "interpersonal, customer orientation, etc.) with their common aliases. Agents "
        "extracting skills from a resume or job posting use it to normalize what they "
        "find to one shared, unified vocabulary."
    ),
    mime_type="application/json",
)
def common_soft_skills() -> dict[str, dict[str, list[str]]]:
    """Returns the canonical soft-skill taxonomy."""
    return COMMON_SOFT_SKILLS
